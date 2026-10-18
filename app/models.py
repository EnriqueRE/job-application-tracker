from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Status(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    NO_RESPONSE = "no_response"


class Channel(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    VIDEO = "video"
    IN_PERSON = "in_person"
    OTHER = "other"


OPEN_STATUSES = frozenset({Status.APPLIED, Status.SCREENING, Status.INTERVIEWING})


def utcnow() -> datetime:
    # Python-side rather than now(): Postgres now() is frozen per transaction, which would
    # give every row written in one request the same timestamp.
    return datetime.now(UTC)


def status_enum(name: str) -> Enum:
    return Enum(
        Status,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda statuses: [s.value for s in statuses],
    )


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (Index("uq_companies_name", text("lower(name)"), unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(2000))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    contacts: Mapped[list["Contact"]] = relationship(
        order_by="(Contact.name, Contact.id)", back_populates="company"
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index(
            "uq_applications_company_title_applied_on",
            "company_id",
            # Postgres's canonical spelling of lower(trim(title)), so `alembic check` matches.
            text("lower(TRIM(BOTH FROM title))"),
            "applied_on",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(300))
    job_url: Mapped[str | None] = mapped_column(String(2000))
    job_description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(200), default="")
    applied_on: Mapped[date] = mapped_column(Date)
    status: Mapped[Status] = mapped_column(status_enum("application_status"))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company: Mapped[Company] = relationship()
    history: Mapped[list["StatusChange"]] = relationship(
        order_by="(StatusChange.changed_on, StatusChange.recorded_at, StatusChange.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    links: Mapped[list["AppLink"]] = relationship(
        order_by="AppLink.id", cascade="all, delete-orphan", passive_deletes=True
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        order_by=(
            "(Interaction.occurred_on.desc(), Interaction.created_at.desc(), Interaction.id.desc())"
        ),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class StatusChange(Base):
    __tablename__ = "status_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[Status | None] = mapped_column(status_enum("status_change_from"))
    to_status: Mapped[Status] = mapped_column(status_enum("status_change_to"))
    changed_on: Mapped[date] = mapped_column(Date)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppLink(Base):
    __tablename__ = "app_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2000))


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str | None] = mapped_column(String(320))
    linkedin_url: Mapped[str | None] = mapped_column(String(2000))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company: Mapped[Company] = relationship(back_populates="contacts")


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    occurred_on: Mapped[date] = mapped_column(Date)
    channel: Mapped[Channel] = mapped_column(
        Enum(
            Channel,
            name="interaction_channel",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda channels: [c.value for c in channels],
        )
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped[Contact | None] = relationship()


class FollowUpThreshold(Base):
    __tablename__ = "follow_up_thresholds"
    __table_args__ = (
        CheckConstraint("days BETWEEN 1 AND 365", name="ck_follow_up_thresholds_days"),
        CheckConstraint(
            "status IN ('applied', 'screening', 'interviewing')",
            name="ck_follow_up_thresholds_open_status",
        ),
    )

    status: Mapped[Status] = mapped_column(
        Enum(
            Status,
            native_enum=False,
            length=20,
            values_callable=lambda statuses: [s.value for s in statuses],
        ),
        primary_key=True,
    )
    days: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
