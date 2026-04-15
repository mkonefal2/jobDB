from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class Source(str, Enum):
    PRACAPL = "pracapl"
    JUSTJOINIT = "justjoinit"
    ROCKETJOBS = "rocketjobs"
    PRACUJ = "pracuj"
    NOFLUFFJOBS = "nofluffjobs"
    JOOBLE = "jooble"


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    UNKNOWN = "unknown"


class SalaryPeriod(str, Enum):
    MONTH = "month"
    HOUR = "hour"
    DAY = "day"
    YEAR = "year"


class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class JobOffer(BaseModel):
    source: Source
    source_id: str
    source_url: str
    title: str
    company_name: str | None = None
    company_logo_url: str | None = None

    location_raw: str | None = None
    location_city: str | None = None
    location_region: str | None = None
    work_mode: WorkMode = WorkMode.UNKNOWN

    seniority: Seniority = Seniority.UNKNOWN
    employment_type: str | None = None

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    salary_type: str | None = None  # brutto / netto

    category: str | None = None
    technologies: list[str] = Field(default_factory=list)
    description_text: str | None = None

    dedup_cluster_id: str | None = None

    published_at: datetime | None = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def id(self) -> str:
        raw = f"{self.source.value}:{self.source_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ScrapedResult(BaseModel):
    source: Source
    started_at: datetime
    finished_at: datetime | None = None
    offers: list[JobOffer] = Field(default_factory=list)
    errors: int = 0
    status: ScrapeStatus = ScrapeStatus.SUCCESS
    pages_scraped: int = 0


class ScrapeLogEntry(BaseModel):
    run_id: str
    source: Source
    started_at: datetime
    finished_at: datetime | None = None
    offers_scraped: int = 0
    offers_new: int = 0
    offers_updated: int = 0
    errors: int = 0
    status: ScrapeStatus = ScrapeStatus.SUCCESS
