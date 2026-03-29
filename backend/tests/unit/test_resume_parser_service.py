from __future__ import annotations

from datetime import datetime

from app.services.resume_parser_service import ResumeParserService


def test_parse_extracts_core_profile_fields_from_sectioned_resume() -> None:
    service = ResumeParserService()
    raw_text = """
    Aditya Sahu
    adityasahu1234@gmail.com
    Senior Backend Engineer

    Technical Skills: Python, FastAPI, PostgreSQL, Docker, Leadership, English

    Professional Experience
    Acme Labs | Senior Backend Engineer | 2021 - Present
    Built high-throughput APIs and reduced latency by 35%.

    Education
    B.Tech Computer Science | National Institute of Technology | 2020
    """

    parsed = service.parse(raw_text)

    assert parsed.name == "Aditya Sahu"
    assert parsed.email == "adityasahu1234@gmail.com"
    assert parsed.current_title == "Senior Backend Engineer"
    assert "Python" in parsed.skills.technical
    assert "FastAPI" in parsed.skills.technical
    assert "PostgreSQL" in parsed.skills.technical
    assert "Docker" in parsed.skills.tools
    assert "Leadership" in parsed.skills.soft
    assert "English" in parsed.skills.languages
    assert parsed.experience
    assert parsed.experience[0].duration_months >= 12
    assert parsed.education
    assert parsed.education[0].institution == "National Institute of Technology"


def test_parse_handles_non_pipe_experience_and_inline_skills() -> None:
    service = ResumeParserService()
    raw_text = """
    Priya Verma
    priya.verma+ml@gmail.com
    Machine Learning Engineer
    Skills: Python, SQL, Airflow, Communication
    Experience
    Machine Learning Engineer at VisionAI 2020 - Present
    Built model monitoring and retraining workflows.
    """

    parsed = service.parse(raw_text)

    assert parsed.email == "priya.verma+ml@gmail.com"
    assert parsed.current_title == "Machine Learning Engineer"
    assert "Python" in parsed.skills.technical
    assert "SQL" in parsed.skills.technical
    assert "Airflow" in parsed.skills.tools
    assert "Communication" in parsed.skills.soft
    assert len(parsed.experience) >= 1
    assert parsed.years_of_experience >= 1


def test_duration_to_months_uses_current_year_for_present_ranges() -> None:
    service = ResumeParserService()

    months = service._duration_to_months("2024 - Present")
    expected = max((datetime.now().year - 2024) * 12, 12)

    assert months == expected
