from __future__ import annotations

from app.schemas.jobs import RawJob


class JobDeduplicator:
    def deduplicate(self, jobs: list[RawJob]) -> list[RawJob]:
        deduplicated: list[RawJob] = []
        seen_urls: set[str] = set()
        seen_company_titles: list[tuple[str, str]] = []

        for job in jobs:
            normalized_url = job.apply_url.strip().lower()
            if normalized_url in seen_urls:
                continue

            normalized_company = _normalize(job.company_name)
            normalized_title = _normalize(job.title)

            if any(
                company == normalized_company and _levenshtein_distance(title, normalized_title) <= 2
                for company, title in seen_company_titles
            ):
                continue

            seen_urls.add(normalized_url)
            seen_company_titles.append((normalized_company, normalized_title))
            deduplicated.append(job)

        return deduplicated


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insertions = previous[j] + 1
            deletions = current[j - 1] + 1
            substitutions = previous[j - 1] + (left_char != right_char)
            current.append(min(insertions, deletions, substitutions))
        previous = current
    return previous[-1]
