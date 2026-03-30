from __future__ import annotations

from typing import Any
from datetime import datetime
import re

import structlog

from app.core.config import Settings, get_settings
from app.core.constants import GEMINI_DEFAULT_CHAT_MODEL
from app.core.logging_safety import log_debug, log_exception, text_snapshot
from app.schemas.resume import (
    EducationEntry,
    ExperienceEntry,
    ParsedResumeProfile,
    SalaryRange,
    SkillGroups,
)
from app.services.gemini_client import GeminiApiError, GeminiClient


logger = structlog.get_logger(__name__)


_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")
_DURATION_PATTERN = re.compile(
    r"(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*(?:-|to|\u2013|\u2014)\s*(?:present|current|ongoing|now|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})",
    flags=re.IGNORECASE,
)
_SECTION_ALIASES = {
    "skills": {"skills", "technical skills", "core skills", "competencies", "technologies", "tech stack"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "career history",
    },
    "education": {"education", "academic background", "academics", "qualifications"},
}
_TITLE_PHRASE_PATTERN = re.compile(
    r"\b(?:senior|lead|principal|staff|junior)?\s*(?:software|backend|frontend|full[ -]?stack|machine learning|data|devops|cloud|ai|ml|product)?\s*(?:engineer|developer|scientist|analyst|manager|architect|consultant|specialist)\b",
    flags=re.IGNORECASE,
)
_TITLE_KEYWORDS = {
    "engineer",
    "developer",
    "scientist",
    "analyst",
    "manager",
    "architect",
    "consultant",
    "specialist",
    "lead",
    "director",
    "intern",
    "recruiter",
    "designer",
    "product",
}
_SOFT_SKILLS = {
    "communication",
    "leadership",
    "collaboration",
    "problem solving",
    "critical thinking",
    "stakeholder management",
    "mentoring",
    "teamwork",
    "ownership",
}
_TOOLS = {
    "docker",
    "kubernetes",
    "terraform",
    "jira",
    "git",
    "github",
    "gitlab",
    "jenkins",
    "tableau",
    "power bi",
    "airflow",
    "snowflake",
    "databricks",
    "figma",
    "notion",
}
_LANGUAGES = {
    "english",
    "hindi",
    "spanish",
    "french",
    "german",
    "mandarin",
    "japanese",
    "arabic",
    "portuguese",
    "bengali",
}
_EDUCATION_KEYWORDS = {
    "university",
    "college",
    "institute",
    "school",
    "academy",
    "bachelor",
    "master",
    "phd",
    "b.tech",
    "b.e",
    "m.tech",
    "mba",
    "bs",
    "ms",
    "bsc",
    "msc",
}
_EDUCATION_PATTERN = re.compile(
    r"\b(?:university|college|institute|school|academy|bachelor|master|phd|b\.?tech|b\.?e|m\.?tech|mba|bs|ms|bsc|msc)\b",
    flags=re.IGNORECASE,
)
_RESUME_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "name",
        "email",
        "current_title",
        "years_of_experience",
        "seniority_level",
        "skills",
        "experience",
        "education",
        "preferred_roles",
        "inferred_salary_range",
        "work_style_signals",
        "summary_for_matching",
    ],
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "current_title": {"type": "string"},
        "years_of_experience": {"type": "integer"},
        "seniority_level": {"type": "string"},
        "skills": {
            "type": "object",
            "required": ["technical", "soft", "tools", "languages"],
            "properties": {
                "technical": {"type": "array", "items": {"type": "string"}},
                "soft": {"type": "array", "items": {"type": "string"}},
                "tools": {"type": "array", "items": {"type": "string"}},
                "languages": {"type": "array", "items": {"type": "string"}},
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["company", "title", "duration_months", "highlights"],
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "duration_months": {"type": "integer"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["degree", "field", "institution", "year"],
                "properties": {
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "institution": {"type": "string"},
                    "year": {"type": ["integer", "null"]},
                },
            },
        },
        "preferred_roles": {"type": "array", "items": {"type": "string"}},
        "inferred_salary_range": {
            "type": "object",
            "required": ["min", "max", "currency"],
            "properties": {
                "min": {"type": "integer"},
                "max": {"type": "integer"},
                "currency": {"type": "string"},
            },
        },
        "work_style_signals": {"type": "array", "items": {"type": "string"}},
        "summary_for_matching": {"type": "string"},
    },
}
_RESUME_SYSTEM_INSTRUCTION = (
    "You are a resume intelligence parser for a job automation product. "
    "Return strict JSON that matches the supplied schema. "
    "Extract only grounded facts from the resume and avoid hallucinations. "
    "If a field is missing, use conservative defaults. "
    "summary_for_matching must be 2-3 sentences in third person, optimized for semantic job matching."
)


class ResumeParserService:
    def __init__(self, *, settings: Settings | None = None, gemini_client: GeminiClient | None = None) -> None:
        resolved_settings = settings or get_settings()
        self._gemini_model = resolved_settings.gemini_chat_model or GEMINI_DEFAULT_CHAT_MODEL
        self._gemini_client = gemini_client or GeminiClient(
            api_key=resolved_settings.gemini_api_key,
            chat_model=self._gemini_model,
            embedding_model=resolved_settings.gemini_embedding_model,
        )

    def parse(self, raw_text: str) -> ParsedResumeProfile:
        normalized_text = self._normalize_text(raw_text)
        log_debug(logger, "resume_parser.parse.start", raw_text=text_snapshot(normalized_text))

        llm_profile = self._parse_with_gemini(normalized_text)
        if llm_profile is not None:
            log_debug(logger, "resume_parser.parse.gemini_success")
            return llm_profile

        log_debug(logger, "resume_parser.parse.heuristic_fallback", reason="gemini_unavailable_or_failed")
        try:
            lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
            sections = self._split_sections(lines)
            header_lines = sections.get("header", [])

            name = self._extract_name(header_lines)
            email = self._extract_email(normalized_text)
            current_title = self._extract_current_title(header_lines, lines)
            skills = self._extract_skills(lines=lines, sections=sections)
            experience = self._extract_experience(lines=lines, sections=sections)
            education = self._extract_education(lines=lines, sections=sections)
            years_of_experience = max(sum(item.duration_months for item in experience) // 12, 1 if experience else 0)
            if years_of_experience == 0:
                years_of_experience = self._infer_years_of_experience(normalized_text)
            seniority_level = self._infer_seniority(current_title)
            preferred_roles = [current_title] if current_title else []
            salary_range = self._infer_salary_range(seniority_level)
            work_style_signals = self._infer_work_style_signals(normalized_text)
            summary = self._build_summary(current_title, skills.technical, years_of_experience)

            log_debug(
                logger,
                "resume_parser.parse.complete",
                lines_count=len(lines),
                skills_count=len(skills.technical),
                experience_entries=len(experience),
                education_entries=len(education),
                years_of_experience=years_of_experience,
                seniority_level=seniority_level,
            )
            return ParsedResumeProfile(
                name=name,
                email=email,
                current_title=current_title,
                years_of_experience=years_of_experience,
                seniority_level=seniority_level,
                skills=skills,
                experience=experience,
                education=education,
                preferred_roles=preferred_roles,
                inferred_salary_range=salary_range,
                work_style_signals=work_style_signals,
                summary_for_matching=summary,
            )
        except Exception as error:
            log_exception(logger, "resume_parser.parse.failed", error, raw_text=text_snapshot(normalized_text))
            raise

    def _parse_with_gemini(self, normalized_text: str) -> ParsedResumeProfile | None:
        if not self._gemini_client.is_configured:
            return None

        prompt = (
            "Parse this resume text and return JSON only.\n\n"
            f"Resume Text:\n{normalized_text}"
        )
        try:
            payload = self._gemini_client.generate_json(
                prompt=prompt,
                system_instruction=_RESUME_SYSTEM_INSTRUCTION,
                schema=_RESUME_JSON_SCHEMA,
                temperature=0.0,
                model=self._gemini_model,
            )
            profile = ParsedResumeProfile.model_validate(payload)
            return profile
        except (GeminiApiError, ValueError) as error:
            log_debug(logger, "resume_parser.parse.gemini_failed", reason=str(error))
            return None
        except Exception as error:
            log_exception(logger, "resume_parser.parse.gemini_unexpected_error", error)
            return None

    def _normalize_text(self, raw_text: str) -> str:
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\u2022", "\n").replace("\u00b7", "\n")
        normalized = re.sub(r"\t+", " ", normalized)
        normalized = re.sub(r"[ ]{2,}", " ", normalized)
        return normalized.strip()

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"header": []}
        current = "header"

        for line in lines:
            header, remainder = self._detect_section_header(line)
            if header:
                current = header
                sections.setdefault(current, [])
                if remainder:
                    sections[current].append(remainder)
                continue

            sections.setdefault(current, []).append(line)

        return sections

    def _detect_section_header(self, line: str) -> tuple[str | None, str | None]:
        normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
        for section, aliases in _SECTION_ALIASES.items():
            for alias in aliases:
                if normalized == alias:
                    return section, None
                if normalized.startswith(alias):
                    if ":" in line:
                        _, remainder = line.split(":", maxsplit=1)
                        return section, remainder.strip()
                    return section, None
                if line.lower().startswith(f"{alias}:"):
                    _, remainder = line.split(":", maxsplit=1)
                    return section, remainder.strip()
        return None, None

    def _extract_name(self, header_lines: list[str]) -> str:
        for line in header_lines[:4]:
            if self._looks_like_contact_line(line):
                continue
            if self._is_probable_name(line):
                return line

        return header_lines[0] if header_lines else "Unknown Candidate"

    def _is_probable_name(self, line: str) -> bool:
        words = [word for word in re.split(r"\s+", line.strip()) if word]
        if len(words) < 2 or len(words) > 5:
            return False
        if any(char.isdigit() for char in line):
            return False
        lowered = line.lower()
        if any(token in lowered for token in ("engineer", "developer", "manager", "analyst", "resume")):
            return False
        return True

    def _looks_like_contact_line(self, line: str) -> bool:
        lowered = line.lower()
        return (
            "@" in line
            or "linkedin" in lowered
            or "github" in lowered
            or "http" in lowered
            or bool(re.search(r"\+?\d[\d\s()\-]{7,}", line))
        )

    def _extract_email(self, raw_text: str) -> str:
        email = ""
        for match in _EMAIL_PATTERN.findall(raw_text):
            candidate = match.strip("<>[](){}.,;:\"")
            if not self._is_valid_email(candidate):
                continue
            email = candidate.lower()
            break
        log_debug(logger, "resume_parser.extract_email", found=bool(email))
        return email

    def _is_valid_email(self, email: str) -> bool:
        local, _, domain = email.partition("@")
        if not local or not domain:
            return False
        if domain.startswith(".") or domain.endswith("."):
            return False
        if ".." in email:
            return False
        if "." not in domain:
            return False
        tld = domain.rsplit(".", maxsplit=1)[-1]
        return len(tld) >= 2

    def _extract_current_title(self, header_lines: list[str], lines: list[str] | None = None) -> str:
        for line in header_lines[1:8]:
            if self._looks_like_contact_line(line):
                continue
            if not line or len(line) > 80:
                continue
            if self._is_probable_title(line):
                formatted = self._format_title(line)
                log_debug(logger, "resume_parser.extract_current_title.found", title=formatted)
                return formatted

        for line in (lines or [])[:40]:
            if self._looks_like_contact_line(line):
                continue
            match = _TITLE_PHRASE_PATTERN.search(line)
            if match:
                inferred = self._format_title(match.group(0))
                log_debug(logger, "resume_parser.extract_current_title.inferred", title=inferred)
                return inferred

        log_debug(logger, "resume_parser.extract_current_title.empty")
        return ""

    def _format_title(self, title: str) -> str:
        acronyms = {"ai", "ml", "nlp", "llm", "ui", "ux", "qa", "sre", "devops"}
        words: list[str] = []
        for word in title.split():
            normalized = re.sub(r"[^A-Za-z]", "", word).casefold()
            if normalized in acronyms:
                words.append(word.upper())
                continue
            if word.isupper() and len(word) <= 5:
                words.append(word)
                continue
            words.append(word.capitalize())
        return " ".join(words)

    def _is_probable_title(self, line: str) -> bool:
        lowered = line.lower()
        if any(alias in lowered for aliases in _SECTION_ALIASES.values() for alias in aliases):
            return False
        if any(char.isdigit() for char in lowered):
            return False
        if ":" in line and len(line.split()) <= 2:
            return False
        words = lowered.split()
        if len(words) < 1 or len(words) > 10:
            return False
        return any(keyword in lowered for keyword in _TITLE_KEYWORDS)

    def _extract_skills(self, *, lines: list[str], sections: dict[str, list[str]]) -> SkillGroups:
        source_lines = sections.get("skills") or [
            line
            for line in lines
            if re.search(r"(?:technical\s+)?skills?|competencies|tech stack|tools|languages\s*:", line, flags=re.IGNORECASE)
        ]
        candidates: list[str] = []

        for line in source_lines:
            if not line:
                continue
            normalized_line = re.sub(r"^(technical\s+)?skills?\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            if not normalized_line:
                continue
            for token in re.split(r",|\||/|;|\u2022", normalized_line):
                skill = self._normalize_skill(token)
                if skill:
                    candidates.append(skill)

        unique_skills = self._deduplicate(candidates)
        if not unique_skills:
            log_debug(logger, "resume_parser.extract_skills.empty")
            return SkillGroups()

        categorized = self._categorize_skills(unique_skills)
        log_debug(
            logger,
            "resume_parser.extract_skills.complete",
            technical=len(categorized.technical),
            soft=len(categorized.soft),
            tools=len(categorized.tools),
            languages=len(categorized.languages),
        )
        return categorized

    def _normalize_skill(self, token: str) -> str:
        cleaned = token.strip().strip("-.:()[]{}")
        if ":" in cleaned:
            _, remainder = cleaned.split(":", maxsplit=1)
            if remainder.strip():
                cleaned = remainder.strip()
        cleaned = re.sub(r"\([^)]*yrs?[^)]*\)", "", cleaned, flags=re.IGNORECASE).strip()
        if len(cleaned) < 2 or len(cleaned) > 40:
            return ""
        if re.search(r"\b(responsible|built|managed|developed|designed)\b", cleaned, flags=re.IGNORECASE):
            return ""
        compact = re.sub(r"\s+", " ", cleaned)
        if compact.isupper() and len(compact) <= 5:
            return compact
        return compact

    def _deduplicate(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _categorize_skills(self, skills: list[str]) -> SkillGroups:
        technical: list[str] = []
        soft: list[str] = []
        tools: list[str] = []
        languages: list[str] = []

        for skill in skills:
            lowered = skill.casefold()
            if lowered in _LANGUAGES:
                languages.append(skill)
            elif lowered in _TOOLS:
                tools.append(skill)
            elif lowered in _SOFT_SKILLS:
                soft.append(skill)
            else:
                technical.append(skill)

        return SkillGroups(technical=technical, soft=soft, tools=tools, languages=languages)

    def _extract_experience(self, *, lines: list[str], sections: dict[str, list[str]]) -> list[ExperienceEntry]:
        entries: list[ExperienceEntry] = []
        source_lines = sections.get("experience") or lines

        for index, line in enumerate(source_lines):
            entry = self._parse_experience_line(line)
            if entry is None:
                continue

            highlights: list[str] = []
            if index + 1 < len(source_lines):
                candidate = source_lines[index + 1]
                if not self._parse_experience_line(candidate) and not self._contains_education_signal(candidate):
                    if len(candidate.split()) >= 5:
                        highlights = [candidate]

            entries.append(entry.model_copy(update={"highlights": highlights}))

        log_debug(logger, "resume_parser.extract_experience.complete", entries=len(entries))
        return entries

    def _parse_experience_line(self, line: str) -> ExperienceEntry | None:
        if not line:
            return None

        if "|" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) >= 2:
                company = parts[0]
                title = parts[1]
                duration = parts[2] if len(parts) >= 3 else line
                return ExperienceEntry(
                    company=company,
                    title=title,
                    duration_months=self._duration_to_months(duration),
                    highlights=[],
                )

        match = _DURATION_PATTERN.search(line)
        if not match:
            return None

        duration = match.group(0)
        before = line[: match.start()].strip(" -|,;:")
        if not before:
            return None
        company, title = self._split_company_and_title(before)
        if not company and not title:
            return None

        return ExperienceEntry(
            company=company or "Unknown Company",
            title=title or "Role",
            duration_months=self._duration_to_months(duration),
            highlights=[],
        )

    def _split_company_and_title(self, text: str) -> tuple[str, str]:
        for separator in ("|", " @ ", " at ", " - ", " -- "):
            if separator in text.lower() if separator.strip() in {"@", "at"} else separator in text:
                if separator.strip() in {"@", "at"}:
                    parts = re.split(r"\s@\s|\sat\s", text, maxsplit=1, flags=re.IGNORECASE)
                else:
                    parts = text.split(separator, maxsplit=1)
                if len(parts) != 2:
                    continue
                left = parts[0].strip()
                right = parts[1].strip()
                if self._is_probable_title(left):
                    return right, left
                return left, right

        if self._is_probable_title(text):
            return "", text
        return text, ""

    def _extract_education(self, *, lines: list[str], sections: dict[str, list[str]]) -> list[EducationEntry]:
        entries: list[EducationEntry] = []
        source_lines = sections.get("education") or lines

        for line in source_lines:
            if re.search(r"hackathon|certification|project|internship|experience|skills", line, flags=re.IGNORECASE):
                continue
            if not self._contains_education_signal(line):
                continue
            parts = [part.strip() for part in re.split(r"\||-|,", line) if part.strip()]
            year_match = _YEAR_PATTERN.search(line)

            degree = ""
            institution = ""
            for part in parts:
                lowered = part.casefold()
                if not degree and any(token in lowered for token in ("bachelor", "master", "phd", "b.tech", "mba", "b.e", "m.tech", "bs", "ms", "bsc", "msc")):
                    degree = part
                    continue
                if not institution and any(token in lowered for token in ("university", "college", "institute", "school", "academy")):
                    institution = part

            if not degree and parts:
                degree = parts[0]
            if not institution and len(parts) > 1:
                institution = parts[1]

            entries.append(
                EducationEntry(
                    degree=degree or line,
                    field="",
                    institution=institution,
                    year=int(year_match.group(0)) if year_match else None,
                )
            )

        log_debug(logger, "resume_parser.extract_education.complete", entries=len(entries))
        return entries

    def _contains_education_signal(self, line: str) -> bool:
        return bool(_EDUCATION_PATTERN.search(line))

    def _duration_to_months(self, duration: str) -> int:
        current_year = datetime.now().year
        years = [int(value) for value in _YEAR_PATTERN.findall(duration)]

        if re.search(r"present|current|ongoing|now", duration, flags=re.IGNORECASE):
            start_year = years[0] if years else current_year - 1
            months = max((current_year - start_year) * 12, 12)
            log_debug(logger, "resume_parser.duration_to_months.present", duration=duration, months=months)
            return months

        if len(years) >= 2:
            months = max((years[-1] - years[0]) * 12, 12)
            log_debug(logger, "resume_parser.duration_to_months.range", duration=duration, months=months)
            return months

        log_debug(logger, "resume_parser.duration_to_months.fallback", duration=duration, months=12)
        return 12

    def _infer_years_of_experience(self, raw_text: str) -> int:
        years = [int(value) for value in _YEAR_PATTERN.findall(raw_text)]
        if not years:
            return 0
        current_year = datetime.now().year
        earliest = min(years)
        if earliest >= current_year:
            return 1
        inferred = current_year - earliest
        return min(max(inferred, 1), 40)

    def _infer_seniority(self, current_title: str) -> str:
        lowered = current_title.lower()
        if "principal" in lowered:
            return "principal"
        if "lead" in lowered:
            return "lead"
        if "senior" in lowered:
            return "senior"
        if "junior" in lowered:
            return "junior"
        return "mid"

    def _infer_salary_range(self, seniority_level: str) -> SalaryRange:
        ranges = {
            "junior": (600000, 1200000),
            "mid": (1200000, 2200000),
            "senior": (2200000, 4000000),
            "lead": (3000000, 5000000),
            "principal": (4000000, 6500000),
        }
        minimum, maximum = ranges.get(seniority_level, ranges["mid"])
        log_debug(
            logger,
            "resume_parser.infer_salary_range",
            seniority_level=seniority_level,
            salary_min=minimum,
            salary_max=maximum,
        )
        return SalaryRange(min=minimum, max=maximum, currency="INR")

    def _infer_work_style_signals(self, raw_text: str) -> list[str]:
        lowered = raw_text.lower()
        signals: list[str] = []
        if "remote" in lowered:
            signals.append("remote-leaning")
        if "startup" in lowered:
            signals.append("startup-experienced")
        if not signals:
            signals.append("collaborative")
        log_debug(logger, "resume_parser.infer_work_style_signals", signals=signals)
        return signals

    def _build_summary(self, current_title: str, technical_skills: list[str], years_of_experience: int) -> str:
        top_skills = ", ".join(technical_skills[:4])
        summary = (
            f"{current_title or 'Technical professional'} with approximately {years_of_experience} years of "
            f"experience. Core strengths include {top_skills or 'software delivery, problem solving, and execution'}."
        )
        log_debug(logger, "resume_parser.build_summary", summary=text_snapshot(summary))
        return summary
