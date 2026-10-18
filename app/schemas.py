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


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: Name
    title: Title
    job_url: Url | None = None
    job_description: str = ""
    location: Short = ""
    source: Short = ""
    applied_on: date
    status: Status = Status.APPLIED
    notes: str = ""


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
