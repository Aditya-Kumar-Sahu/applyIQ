from __future__ import annotations

import re

from app.schemas.resume import (
    EducationEntry,
    ExperienceEntry,
    ParsedResumeProfile,
    SalaryRange,
    SkillGroups,
)


class ResumeParserService:
    def parse(self, raw_text: str) -> ParsedResumeProfile:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        name = lines[0] if lines else "Unknown Candidate"
        email = self._extract_email(raw_text)
        current_title = self._extract_current_title(lines)
        technical_skills = self._extract_skills(raw_text)
        experience = self._extract_experience(lines)
        education = self._extract_education(lines)
        years_of_experience = max(sum(item.duration_months for item in experience) // 12, 1 if experience else 0)
        seniority_level = self._infer_seniority(current_title)
        preferred_roles = [current_title] if current_title else []
        salary_range = self._infer_salary_range(seniority_level)
        work_style_signals = self._infer_work_style_signals(raw_text)
        summary = self._build_summary(current_title, technical_skills, years_of_experience)

        return ParsedResumeProfile(
            name=name,
            email=email,
            current_title=current_title,
            years_of_experience=years_of_experience,
            seniority_level=seniority_level,
            skills=SkillGroups(technical=technical_skills),
            experience=experience,
            education=education,
            preferred_roles=preferred_roles,
            inferred_salary_range=salary_range,
            work_style_signals=work_style_signals,
            summary_for_matching=summary,
        )

    def _extract_email(self, raw_text: str) -> str:
        match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", raw_text)
        return match.group(0) if match else ""

    def _extract_current_title(self, lines: list[str]) -> str:
        for line in lines[1:5]:
            if "@" in line:
                continue
            if line.lower() in {"experience", "education"}:
                continue
            if "|" not in line and ":" not in line:
                return line
        return ""

    def _extract_skills(self, raw_text: str) -> list[str]:
        match = re.search(r"skills:\s*(.+)", raw_text, flags=re.IGNORECASE)
        if not match:
            return []
        return [skill.strip() for skill in match.group(1).split(",") if skill.strip()]

    def _extract_experience(self, lines: list[str]) -> list[ExperienceEntry]:
        entries: list[ExperienceEntry] = []

        for index, line in enumerate(lines):
            if "|" not in line:
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 3:
                continue
            company, title, duration = parts[:3]
            duration_months = self._duration_to_months(duration)
            highlights: list[str] = []
            if index + 1 < len(lines) and "|" not in lines[index + 1]:
                highlights = [lines[index + 1]]
            entries.append(
                ExperienceEntry(
                    company=company,
                    title=title,
                    duration_months=duration_months,
                    highlights=highlights,
                )
            )

        return entries

    def _extract_education(self, lines: list[str]) -> list[EducationEntry]:
        entries: list[EducationEntry] = []

        for line in lines:
            if "university" not in line.lower() and "college" not in line.lower():
                continue
            parts = [part.strip() for part in line.split("|")]
            degree = parts[0] if parts else line
            institution = parts[1] if len(parts) > 1 else ""
            year_match = re.search(r"(19|20)\d{2}", line)
            entries.append(
                EducationEntry(
                    degree=degree,
                    field="",
                    institution=institution,
                    year=int(year_match.group(0)) if year_match else None,
                )
            )

        return entries

    def _duration_to_months(self, duration: str) -> int:
        if "present" in duration.lower():
            start_match = re.search(r"(19|20)\d{2}", duration)
            start_year = int(start_match.group(0)) if start_match else 2024
            return max((2026 - start_year) * 12, 12)

        years = re.findall(r"(19|20)\d{2}", duration)
        if len(years) >= 2:
            return max((int(years[1]) - int(years[0])) * 12, 12)

        return 12

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
        return signals

    def _build_summary(self, current_title: str, technical_skills: list[str], years_of_experience: int) -> str:
        top_skills = ", ".join(technical_skills[:4])
        return (
            f"{current_title or 'Technical professional'} with approximately {years_of_experience} years of "
            f"experience. Core strengths include {top_skills or 'software delivery, problem solving, and execution'}."
        )
