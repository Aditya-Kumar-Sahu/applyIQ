from __future__ import annotations

from pydantic import BaseModel, Field


class SkillGroups(BaseModel):
    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    company: str
    title: str
    duration_months: int
    highlights: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    degree: str
    field: str
    institution: str
    year: int | None = None


class SalaryRange(BaseModel):
    min: int
    max: int
    currency: str


class ParsedResumeProfile(BaseModel):
    name: str
    email: str
    current_title: str
    years_of_experience: int
    seniority_level: str
    skills: SkillGroups
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    inferred_salary_range: SalaryRange
    work_style_signals: list[str] = Field(default_factory=list)
    summary_for_matching: str


class SearchPreferencesPayload(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str = "any"
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str = "USD"
    excluded_companies: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    is_active: bool = True


class ResumeUploadData(BaseModel):
    profile: ParsedResumeProfile
    file_hash: str
    embedding_dimensions: int


class ResumeDetailData(BaseModel):
    profile: ParsedResumeProfile
    preferences: SearchPreferencesPayload | None


class SearchPreferencesData(BaseModel):
    preferences: SearchPreferencesPayload


class ProfileCompletenessData(BaseModel):
    score: int
    missing_fields: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
