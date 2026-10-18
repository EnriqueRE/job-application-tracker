from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

from app.models import Status

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_http_url = TypeAdapter(HttpUrl)


def _check_url(value: str) -> str:
    # Validate with HttpUrl but keep what was typed, since HttpUrl normalizes (trailing slash).
    _http_url.validate_python(value)
    return value


Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000), AfterValidator(_check_url)
]


class ApplicationFields(BaseModel):
    """Every editable field of an application; status changes go through the status service."""

    model_config = ConfigDict(extra="forbid")

    company: Name
    title: Title
    job_url: Url | None = None
    job_description: str = ""
    location: Short = ""
    source: Short = ""
    applied_on: date
    notes: str = ""


class ApplicationCreate(ApplicationFields):
    status: Status = Status.APPLIED


class ApplicationUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    company: Name | None = None
    title: Title | None = None
    job_url: Url | None = None
    job_description: str | None = None
    location: Short | None = None
    source: Short | None = None
    applied_on: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def only_job_url_can_be_cleared(self) -> "ApplicationUpdate":
        nulled = [
            name
            for name in self.model_fields_set
            if name != "job_url" and getattr(self, name) is None
        ]
        if nulled:
            raise ValueError(f"These fields can't be null: {', '.join(sorted(nulled))}")
        return self


class StatusChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    changed_on: date | None = Field(default=None, description="Defaults to today.")


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StatusChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: Status | None
    to_status: Status
    changed_on: date
    recorded_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: CompanyOut
    title: str
    job_url: str | None
    job_description: str
    location: str
    source: str
    applied_on: date
    status: Status
    notes: str
    history: list[StatusChangeOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DuplicateOut(BaseModel):
    detail: str
    existing_id: int
