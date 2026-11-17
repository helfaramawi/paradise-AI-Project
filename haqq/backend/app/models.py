"""HAQQ relational data model.

Every tenant-owned table carries ``org_id``; every project-owned table carries ``project_id``.
All queries go through :mod:`app.core.tenancy` helpers that filter on ``org_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .db import Base

EMBED_DIM = get_settings().embedding_dim
Money = Numeric(18, 2)


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


# ---------------------------------------------------------------- tenancy & commercial


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str | None] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    country: Mapped[str] = mapped_column(String(2), default="EG")
    default_currency: Mapped[str] = mapped_column(String(3), default="EGP")
    default_language: Mapped[str] = mapped_column(String(2), default="ar")
    # Python weekday numbers: Mon=0 … Sun=6. Egypt: Friday(4) + Saturday(5).
    weekend_days: Mapped[list] = mapped_column(JSON, default=lambda: [4, 5])
    holidays: Mapped[list] = mapped_column(JSON, default=list)  # ISO dates
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("14.00"))
    # AI data-processing policy: may document text be sent to an external model provider?
    ai_external_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=3650)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BusinessUnit(TimestampMixin, Base):
    __tablename__ = "business_units"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str | None] = mapped_column(String(200))


class Plan(Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    name_ar: Mapped[str] = mapped_column(String(80))
    price_monthly: Mapped[Decimal] = mapped_column(Money)
    price_annual: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    max_users: Mapped[int] = mapped_column(Integer)
    max_projects: Mapped[int] = mapped_column(Integer)
    max_documents_month: Mapped[int] = mapped_column(Integer)
    max_pages_month: Mapped[int] = mapped_column(Integer)
    max_ai_tokens_month: Mapped[int] = mapped_column(Integer)
    features: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(20), default="trial")  # trial|active|past_due|cancelled
    billing_cycle: Mapped[str] = mapped_column(String(10), default="monthly")  # monthly|annual
    started_at: Mapped[date] = mapped_column(Date)
    renews_at: Mapped[date] = mapped_column(Date)
    trial_ends_at: Mapped[date | None] = mapped_column(Date)
    plan: Mapped[Plan] = relationship()


class BillingRecord(TimestampMixin, Base):
    __tablename__ = "billing_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    plan_code: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Money)
    vat_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    status: Mapped[str] = mapped_column(String(20), default="issued")  # issued|paid|void
    provider: Mapped[str] = mapped_column(String(30), default="manual")
    reference: Mapped[str | None] = mapped_column(String(120))


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(40))  # documents|pages|ocr_pages|ai_tokens|claim_documents
    quantity: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


# ---------------------------------------------------------------- identity


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(2), default="ar")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship()


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))


# ---------------------------------------------------------------- projects


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("org_id", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    business_unit_id: Mapped[str | None] = mapped_column(ForeignKey("business_units.id", ondelete="SET NULL"))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(250))
    name_ar: Mapped[str | None] = mapped_column(String(250))
    classification: Mapped[str] = mapped_column(String(40), default="building")
    location: Mapped[str | None] = mapped_column(String(200))
    employer_name: Mapped[str | None] = mapped_column(String(200))
    contractor_name: Mapped[str | None] = mapped_column(String(200))
    engineer_name: Mapped[str | None] = mapped_column(String(200))
    contract_form: Mapped[str | None] = mapped_column(String(80))
    contract_value: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    start_date: Mapped[date | None] = mapped_column(Date)
    original_completion_date: Mapped[date | None] = mapped_column(Date)
    current_completion_date: Mapped[date | None] = mapped_column(Date)
    contract_status: Mapped[str] = mapped_column(String(30), default="in_execution")
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    project_role: Mapped[str] = mapped_column(String(40), default="member")


# ---------------------------------------------------------------- documents


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(400))
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_version_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    declared_type: Mapped[str | None] = mapped_column(String(40))  # what the uploader said
    doc_type: Mapped[str | None] = mapped_column(String(40))  # classifier result (or declared)
    doc_type_confidence: Mapped[float | None] = mapped_column()
    language: Mapped[str | None] = mapped_column(String(8))
    doc_date: Mapped[date | None] = mapped_column(Date)
    author_party: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|processing|processed|failed
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[str | None] = mapped_column(String(40))
    ocr_pages: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    security_flags: Mapped[list] = mapped_column(JSON, default=list)  # e.g. prompt-injection markers
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20))  # text|ocr|docx|xlsx|email
    page_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBED_DIM))


class BoqItem(Base):
    __tablename__ = "boq_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    sheet: Mapped[str] = mapped_column(String(100))
    row_number: Mapped[int] = mapped_column(Integer)
    item_ref: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(30))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal | None] = mapped_column(Money)


class DocumentAccessLog(Base):
    __tablename__ = "document_access_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(30))  # view|download|upload|delete
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- contract intelligence


class Clause(TimestampMixin, Base):
    __tablename__ = "clauses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    clause_number: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(400))
    parent_title: Mapped[str | None] = mapped_column(String(400))
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="en")
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    page_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(40), index=True)
    secondary_categories: Mapped[list] = mapped_column(JSON, default=list)
    obligations: Mapped[list] = mapped_column(JSON, default=list)
    entitlements: Mapped[list] = mapped_column(JSON, default=list)
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    time_limits: Mapped[list] = mapped_column(JSON, default=list)  # notice periods, payment periods…
    exclusions: Mapped[list] = mapped_column(JSON, default=list)
    percentages: Mapped[list] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(default=0.0)
    extraction_method: Mapped[str] = mapped_column(String(20), default="rules")
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    verified_by: Mapped[str | None] = mapped_column(String(36))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBED_DIM))


# ---------------------------------------------------------------- events


class ProjectEvent(TimestampMixin, Base):
    __tablename__ = "project_events"
    __table_args__ = (UniqueConstraint("project_id", "ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date)
    awareness_date: Mapped[date | None] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(40))
    category_source: Mapped[str] = mapped_column(String(10), default="user")  # user|ai
    suggested_category: Mapped[str | None] = mapped_column(String(40))
    suggested_category_confidence: Mapped[float | None] = mapped_column()
    responsible_party: Mapped[str | None] = mapped_column(String(30))
    impacted_activities: Mapped[list] = mapped_column(JSON, default=list)
    est_cost_impact: Mapped[Decimal | None] = mapped_column(Money)
    est_time_impact_days: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|under_review|closed
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class EventDocument(Base):
    __tablename__ = "event_documents"
    event_id: Mapped[str] = mapped_column(ForeignKey("project_events.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    link_source: Mapped[str] = mapped_column(String(10), default="user")  # user|ai
    relevance: Mapped[float | None] = mapped_column()
    rationale: Mapped[str | None] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)


class EventClauseLink(Base):
    __tablename__ = "event_clause_links"
    event_id: Mapped[str] = mapped_column(ForeignKey("project_events.id", ondelete="CASCADE"), primary_key=True)
    clause_id: Mapped[str] = mapped_column(ForeignKey("clauses.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    score: Mapped[float] = mapped_column()
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    link_source: Mapped[str] = mapped_column(String(10), default="ai")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- entitlements


class Entitlement(TimestampMixin, Base):
    __tablename__ = "entitlements"
    __table_args__ = (UniqueConstraint("project_id", "ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("project_events.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(20))
    entitlement_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    # potential|insufficient_evidence|requires_expert_verification|substantiated|rejected
    status: Mapped[str] = mapped_column(String(40), index=True)
    primary_clause_id: Mapped[str | None] = mapped_column(ForeignKey("clauses.id", ondelete="SET NULL"))
    related_clause_ids: Mapped[list] = mapped_column(JSON, default=list)
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    evidence_available: Mapped[list] = mapped_column(JSON, default=list)
    evidence_missing: Mapped[list] = mapped_column(JSON, default=list)
    evidence_completeness: Mapped[float] = mapped_column(default=0.0)
    financial_impact: Mapped[Decimal | None] = mapped_column(Money)
    financial_basis: Mapped[str] = mapped_column(String(30), default="not_quantified")
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    time_impact_days: Mapped[int | None] = mapped_column(Integer)
    notice: Mapped[dict] = mapped_column(JSON, default=dict)
    exclusions: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(String(10), default="medium")
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(default=0.0)
    confidence_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[list] = mapped_column(JSON, default=list)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    narrative: Mapped[dict | None] = mapped_column(JSON)
    recommended_actions: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|accepted|rejected|needs_info
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str] = mapped_column(String(20))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Valuation(TimestampMixin, Base):
    __tablename__ = "valuations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    entitlement_id: Mapped[str] = mapped_column(ForeignKey("entitlements.id", ondelete="CASCADE"), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    fx_rate_to_egp: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("1"))
    overhead_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))
    profit_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))
    vat_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("14"))
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    contractual_basis_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|verified
    totals: Mapped[dict] = mapped_column(JSON, default=dict)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(36))
    verified_by: Mapped[str | None] = mapped_column(String(36))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list[ValuationLine]] = relationship(
        cascade="all, delete-orphan", order_by="ValuationLine.position"
    )


class ValuationLine(Base):
    __tablename__ = "valuation_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    valuation_id: Mapped[str] = mapped_column(ForeignKey("valuations.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    # labour|equipment|material|subcontractor|direct_work|site_overheads|prolongation|other
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    unit: Mapped[str | None] = mapped_column(String(30))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    source_document_id: Mapped[str | None] = mapped_column(String(36))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_note: Mapped[str | None] = mapped_column(Text)
    rate_basis: Mapped[str] = mapped_column(String(30), default="user_input")  # boq_rate|invoice|user_input|estimate


# ---------------------------------------------------------------- claims


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("project_id", "ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    entitlement_id: Mapped[str | None] = mapped_column(ForeignKey("entitlements.id", ondelete="SET NULL"))
    ref: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    claim_type: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(40), index=True)
    claimed_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    approved_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    collected_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EGP")
    eot_claimed_days: Mapped[int | None] = mapped_column(Integer)
    eot_approved_days: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[date | None] = mapped_column(Date)
    responded_at: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ClaimStageHistory(Base):
    __tablename__ = "claim_stage_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[str | None] = mapped_column(String(40))
    to_stage: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[str | None] = mapped_column(String(36))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClaimDocument(Base):
    __tablename__ = "claim_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # notice|delay_notice|variation|eot|cost|package|worksheet
    fmt: Mapped[str] = mapped_column(String(10))
    language: Mapped[str] = mapped_column(String(2))
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    generated_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- deadlines & notifications


class Deadline(TimestampMixin, Base):
    __tablename__ = "deadlines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    entitlement_id: Mapped[str | None] = mapped_column(ForeignKey("entitlements.id", ondelete="CASCADE"))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    clause_id: Mapped[str | None] = mapped_column(ForeignKey("clauses.id", ondelete="SET NULL"))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("project_events.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    deadline_type: Mapped[str] = mapped_column(String(30))  # notice|detailed_claim|response|payment|milestone|retention|other
    trigger_date: Mapped[date | None] = mapped_column(Date)
    trigger_description: Mapped[str | None] = mapped_column(Text)
    period_days: Mapped[int | None] = mapped_column(Integer)
    day_type: Mapped[str | None] = mapped_column(String(20))  # calendar|working|unspecified
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    certainty: Mapped[str] = mapped_column(String(20))  # determined|estimated|ambiguous|manual|undetermined
    uncertainty_notes: Mapped[list] = mapped_column(JSON, default=list)
    calculation: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|completed|waived
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    dedupe_key: Mapped[str | None] = mapped_column(String(200), index=True)
    email_status: Mapped[str] = mapped_column(String(20), default="not_sent")  # not_sent|sent|not_configured|failed
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- AI ops, jobs, audit


class AiRun(Base):
    __tablename__ = "ai_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36))
    task: Mapped[str] = mapped_column(String(60))
    prompt_id: Mapped[str] = mapped_column(String(60))
    prompt_version: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))  # ok|invalid_output|error|refused|skipped
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    seq: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    org_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


Index("ix_chunks_project_doc", DocumentChunk.project_id, DocumentChunk.document_id)
Index("ix_deadlines_org_status_due", Deadline.org_id, Deadline.status, Deadline.due_date)
