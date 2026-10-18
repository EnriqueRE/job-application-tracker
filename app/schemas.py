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

from app.models import Channel, Status

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_http_url = TypeAdapter(HttpUrl)


def _check_url(value: str) -> str:
    # Validate with HttpUrl but keep what was typed, since HttpUrl normalizes (trailing slash).
    _http_url.validate_python(value)
    return value


# Deliberately loose: catches typos without pulling in an email-validation dependency.
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]

Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000), AfterValidator(_check_url)
]


def reject_nulls(model: BaseModel, *, nullable: set[str]) -> None:
    """In a partial update, an explicit null may only clear a nullable column."""
    nulled = [
        name
        for name in model.model_fields_set
        if name not in nullable and getattr(model, name) is None
    ]
    if nulled:
        raise ValueError(f"These fields can't be null: {', '.join(sorted(nulled))}")


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
        reject_nulls(self, nullable={"job_url"})
        return self


class StatusChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    changed_on: date | None = Field(default=None, description="Defaults to today.")


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    url: Url


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    url: str


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    title: Short = ""
    email: Email | None = None
    linkedin_url: Url | None = None
    notes: str = ""


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    title: Short | None = None
    email: Email | None = None
    linkedin_url: Url | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def only_links_can_be_cleared(self) -> "ContactUpdate":
        reject_nulls(self, nullable={"email", "linkedin_url"})
        return self


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    title: str
    email: str | None
    linkedin_url: str | None
    notes: str
    created_at: datetime
    updated_at: datetime


class InteractionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_on: date | None = Field(default=None, description="Defaults to today.")
    channel: Channel
    contact_id: int | None = None
    note: str = ""


class ContactRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_on: date
    channel: Channel
    contact: ContactRef | None
    note: str
    created_at: datetime


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
    links: list[LinkOut] = Field(default_factory=list)
    interactions: list[InteractionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DuplicateOut(BaseModel):
    detail: str
    existing_id: int
