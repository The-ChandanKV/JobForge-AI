import os
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, field_validator, model_validator

from .models import uid

Category = Literal["personal", "education", "experience", "skill", "project", "authorization", "certification", "other"]


class Fact(BaseModel):
    id: str = Field(default_factory=uid, pattern=r"^[a-f0-9]{32}$")
    category: Category
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1500)
    verified: bool = False
    unsupported: bool = False
    prioritized: bool = False
    source: str = Field(default="manual", max_length=120)
    excerpt: str = Field(default="", max_length=1500)


    @model_validator(mode="after")
    def validate_evidence_state(self):
        if self.unsupported:
            self.verified = False
        if self.category != "project" or not self.verified:
            self.prioritized = False
        return self


class Preferences(BaseModel):
    roles: list[str] = Field(default_factory=list, max_length=40)
    locations: list[str] = Field(default_factory=list, max_length=40)
    work_modes: list[Literal["remote", "hybrid", "onsite"]] = []
    employment: list[str] = []
    levels: list[str] = []
    excluded_keywords: list[str] = []
    excluded_roles: list[str] = Field(default_factory=list, max_length=40)
    target_companies: list[str] = []
    excluded_companies: list[str] = []
    min_salary: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="", max_length=3)
    recent_days: int | None = Field(default=None, ge=1, le=365)
    relocation: str = Field(default="", max_length=160)
    career_tracks: list[Literal["entry-level", "graduate", "backend", "full-stack", "data", "ai-ml", "internship"]] = []
    exclude_senior_roles: bool = False
    minimum_mandatory_years: int | None = Field(default=None, ge=0, le=30)
    maximum_mandatory_years: int | None = Field(default=None, ge=0, le=30)


class ProfileInput(BaseModel):
    facts: list[Fact] = Field(default_factory=list, max_length=220)
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("facts")
    @classmethod
    def unique_facts(cls, facts):
        if len({fact.id for fact in facts}) != len(facts):
            raise ValueError("Fact IDs must be unique")
        return facts


class Source(BaseModel):
    provider: Literal["greenhouse", "lever", "ashby", "mock"]
    board: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    company: str = Field(min_length=1, max_length=150)
    enabled: bool = True


class PolicyRequest(BaseModel):
    integration: Literal["greenhouse"] = "greenhouse"
    employer: str = Field(min_length=1, max_length=150)
    job_keys: list[str] = Field(min_length=1, max_length=100)
    fact_ids: list[str] = Field(min_length=1, max_length=220)
    expires: AwareDatetime
    daily_limit: int = Field(ge=1, le=100)
    minimum_score: int = Field(default=80, ge=0, le=100)
    acknowledge: Literal[True]


class SubmissionPolicy(BaseModel):
    id: str = Field(default_factory=uid)
    integration: Literal["greenhouse"]
    board: str
    employer: str
    job_keys: list[str]
    approved_facts: dict[str, str]
    form_digests: dict[str, str]
    posting_digests: dict[str, str]
    evidence: str
    expires: AwareDatetime
    created: datetime
    revoked: datetime | None = None
    daily_limit: int
    minimum_score: int


class Options(BaseModel):
    enabled: bool = True
    interval_minutes: int = Field(default=60, ge=1, le=1440)
    min_match_score: int = Field(default=80, ge=0, le=100)
    max_applications_per_day: int = Field(default=5, ge=0, le=100)
    max_submissions_per_day: int = Field(default=5, ge=0, le=100)
    max_resume_generations_per_run: int = Field(default=10, ge=0, le=50)
    auto_submit: bool = False
    require_approval: Literal[True] = True
    dry_run: bool = True
    skip_duplicates: Literal[True] = True
    retry_failed_jobs: bool = True
    max_job_attempts: int = Field(default=3, ge=1, le=8)
    exception_notifications: bool = True
    desktop_notifications: bool = True
    approval_email: bool = False
    notification_interval_minutes: int = Field(default=15, ge=1, le=1440)
    automation_mode: Literal["AUTONOMOUS_PREPARATION", "AUTHORIZED_AUTO_SUBMIT"] = Field(
        default_factory=lambda: os.getenv("AUTOMATION_MODE", "AUTONOMOUS_PREPARATION"), validate_default=True
    )
    submission_policy: SubmissionPolicy | None = None
    mode: Literal["MANUAL", "ASSISTED", "AUTHORIZED_AUTO"] = "ASSISTED"
    provider: Literal["ollama", "rules", "anthropic", "openai"] | None = None
    model: str = Field(default="", max_length=150)
    timezone: str = "Asia/Kolkata"
    sources: list[Source] = Field(default_factory=list, max_length=20)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone, such as Asia/Kolkata") from exc
        return value


class Posting(BaseModel):
    source_key: str = Field(max_length=300)
    source: str
    company: str = Field(min_length=1, max_length=240)
    role: str = Field(min_length=1, max_length=300)
    location: str = ""
    work_mode: str = ""
    employment: str = ""
    description: str = Field(min_length=1, max_length=100_000)
    original_description: str = ""
    url: HttpUrl | None = None
    apply_url: HttpUrl | None = None
    posted: str | None = None
    deadline: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""


class Intake(BaseModel):
    company: str = Field(default="Manual entry", max_length=240)
    role: str = Field(default="Untitled role", max_length=300)
    description: str = Field(default="", max_length=100_000)
    url: HttpUrl | None = None


class Generation(BaseModel):
    template: Literal["classic", "compact"] = "classic"
    instructions: str = Field(default="", max_length=1200)
    parent_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class Edit(BaseModel):
    tex: str = Field(min_length=1, max_length=70_000)
