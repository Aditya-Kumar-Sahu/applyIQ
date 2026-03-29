from __future__ import annotations

import re

import structlog

from pydantic import BaseModel

from app.core.logging_safety import log_debug, log_exception
from app.models.job import Job
from app.schemas.resume import ParsedResumeProfile


logger = structlog.get_logger(__name__)


class CoverLetterDraft(BaseModel):
    cover_letter: str
    tone: str
    word_count: int


class CoverLetterService:
    _BANNED_PHRASES = (
        "I am writing to express my interest",
        "I believe I would be a great fit",
        "Please find attached",
    )

    def generate(
        self,
        *,
        job: Job,
        resume: ParsedResumeProfile,
        matched_skills: list[str],
        tone: str = "formal",
        variant: int = 1,
    ) -> CoverLetterDraft:
        log_debug(
            logger,
            "cover_letter.generate.start",
            job_id=job.id,
            tone=tone,
            variant=variant,
            matched_skills_count=len(matched_skills),
        )
        try:
            company_focus = self._company_focus(job=job, matched_skills=matched_skills, variant=variant)
            achievement = self._achievement(resume)
            candidate_hook = self._candidate_hook(resume=resume, matched_skills=matched_skills)

            if tone == "conversational":
                body = (
                    f"{job.company_name}'s push to {company_focus} grabbed me right away. "
                    f"In my current work as a {resume.current_title}, I {achievement} "
                    f"That mix of measurable delivery and platform ownership is why the {job.title} role feels like a sharp fit. "
                    f"{candidate_hook} I do my best work on teams that care about reliable systems, clear product impact, and fast iteration, "
                    f"which is exactly what I see in {job.company_name}'s approach."
                )
            else:
                body = (
                    f"What stands out about {job.company_name} is {company_focus}. "
                    f"As a {resume.current_title} with {resume.years_of_experience} years of experience, I {achievement} "
                    f"That foundation aligns well with the {job.title} role, particularly where {candidate_hook.lower()} "
                    f"I would value the opportunity to help {job.company_name} continue shipping dependable systems with strong engineering discipline."
                )

            text = self._finalize(body)
            word_count = self.word_count(text)
            log_debug(
                logger,
                "cover_letter.generate.complete",
                job_id=job.id,
                tone=tone,
                word_count=word_count,
            )
            return CoverLetterDraft(
                cover_letter=text,
                tone=tone,
                word_count=word_count,
            )
        except Exception as error:
            log_exception(
                logger,
                "cover_letter.generate.failed",
                error,
                job_id=job.id,
                tone=tone,
                variant=variant,
            )
            raise

    def next_tone(self, previous_tone: str | None) -> str:
        if previous_tone == "formal":
            log_debug(logger, "cover_letter.next_tone", previous_tone=previous_tone, next_tone="conversational")
            return "conversational"
        log_debug(logger, "cover_letter.next_tone", previous_tone=previous_tone, next_tone="formal")
        return "formal"

    def word_count(self, text: str) -> int:
        count = len([word for word in text.split() if word.strip()])
        log_debug(logger, "cover_letter.word_count", count=count)
        return count

    def _company_focus(self, *, job: Job, matched_skills: list[str], variant: int) -> str:
        focus_options = [
            f"build production ML systems on a {self._stack_phrase(matched_skills)} stack",
            f"turn platform engineering into a real advantage for {job.title.lower()} teams",
            f"pair backend reliability with machine learning execution at scale",
        ]
        index = (variant - 1) % len(focus_options)
        focus = focus_options[index]
        log_debug(logger, "cover_letter.company_focus", job_id=job.id, variant=variant, selected_index=index)
        return focus

    def _stack_phrase(self, matched_skills: list[str]) -> str:
        preferred = matched_skills[:2]
        if preferred:
            return " and ".join(preferred)
        return "Python and FastAPI"

    def _achievement(self, resume: ParsedResumeProfile) -> str:
        for entry in resume.experience:
            for highlight in entry.highlights:
                if re.search(r"\d", highlight):
                    log_debug(logger, "cover_letter.achievement.numeric_highlight")
                    return highlight.rstrip(".") + "."
        return (
            f"have spent {resume.years_of_experience} years delivering production systems "
            f"across {', '.join(resume.skills.technical[:3]) or 'modern backend stacks'}."
        )

    def _candidate_hook(self, *, resume: ParsedResumeProfile, matched_skills: list[str]) -> str:
        skill_phrase = ", ".join(matched_skills[:3] or resume.skills.technical[:3])
        return f"my hands-on work across {skill_phrase} would let me contribute quickly"

    def _finalize(self, text: str) -> str:
        normalized = " ".join(text.split())
        for phrase in self._BANNED_PHRASES:
            normalized = normalized.replace(phrase, "")

        words = normalized.split()
        if len(words) > 250:
            normalized = " ".join(words[:250]).rstrip(".") + "."

        log_debug(logger, "cover_letter.finalize", output_length=len(normalized), words=len(normalized.split()))
        return normalized.strip()
