"""Pydantic request/response schemas. All API inputs are validated here; outputs use from_attributes models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .core.rbac import ROLES
from .engines.taxonomy import EVENT_CATEGORIES
from .engines.valuation import CATEGORIES as COST_CATEGORIES

Lang = Literal["en", "ar"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / org


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    mfa_code: str | None = Field(default=None, max_length=10)


class RegisterIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    company_name_ar: str | None = Field(default=None, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    language: Lang = "ar"
    plan_code: Literal["project", "business", "enterprise"] = "business"


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    title: str | None
    language: str
    is_active: bool
    mfa_enabled: bool
    is_platform_admin: bool
    last_login_at: datetime | None


class OrgOut(ORM):
    id: str
    name: str
    name_ar: str | None
    slug: str
    default_currency: str
    default_language: str
    weekend_days: list[int]
    holidays: list[str]
    vat_rate: Decimal
    ai_external_processing: bool
    data_retention_days: int
    onboarding_completed: bool
    is_demo: bool


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    default_language: Lang | None = None
    weekend_days: list[int] | None = None
    holidays: list[date] | None = None
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    ai_external_processing: bool | None = None
    data_retention_days: int | None = Field(default=None, ge=30, le=36500)
    onboarding_completed: bool | None = None

    @field_validator("weekend_days")
    @classmethod
    def _wd(cls, v):
        if v is not None and (any(d < 0 or d > 6 for d in v) or len(v) > 3):
            raise ValueError("weekend_days must be 0-6 (Mon=0) and at most 3 days")
        return v


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    role: str
    title: str | None = Field(default=None, max_length=120)
    language: Lang = "ar"
    password: str = Field(min_length=10, max_length=200)

    @field_validator("role")
    @classmethod
    def _role(cls, v):
        if v not in ROLES:
            raise ValueError("Unknown role")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    role: str | None = None
    title: str | None = Field(default=None, max_length=120)
    language: Lang | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def _role(cls, v):
        if v is not None and v not in ROLES:
            raise ValueError("Unknown role")
        return v


# ---------------------------------------------------------------- projects


class ProjectIn(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9\-_/]+$")
    name: str = Field(min_length=2, max_length=250)
    name_ar: str | None = Field(default=None, max_length=250)
    classification: str = Field(default="building", max_length=40)
    location: str | None = Field(default=None, max_length=200)
    employer_name: str | None = Field(default=None, max_length=200)
    contractor_name: str | None = Field(default=None, max_length=200)
    engineer_name: str | None = Field(default=None, max_length=200)
    contract_form: str | None = Field(default=None, max_length=80)
    contract_value: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("1e14"))
    currency: str = Field(default="EGP", pattern=r"^[A-Z]{3}$")
    start_date: date | None = None
    original_completion_date: date | None = None
    current_completion_date: date | None = None
    contract_status: str = Field(default="in_execution", max_length=30)
    manager_id: str | None = None
    business_unit_id: str | None = None


class ProjectUpdate(ProjectIn):
    code: str | None = Field(default=None, max_length=40)  # type: ignore[assignment]
    name: str | None = Field(default=None, max_length=250)  # type: ignore[assignment]


class ProjectOut(ORM):
    id: str
    code: str
    name: str
    name_ar: str | None
    classification: str
    location: str | None
    employer_name: str | None
    contractor_name: str | None
    engineer_name: str | None
    contract_form: str | None
    contract_value: Decimal
    currency: str
    start_date: date | None
    original_completion_date: date | None
    current_completion_date: date | None
    contract_status: str
    manager_id: str | None
    business_unit_id: str | None
    is_demo: bool
    created_at: datetime


class MemberIn(BaseModel):
    user_id: str
    project_role: str = Field(default="member", max_length=40)


# ---------------------------------------------------------------- documents & clauses


class DocumentOut(ORM):
    id: str
    project_id: str
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    version: int
    previous_version_id: str | None
    is_latest: bool
    declared_type: str | None
    doc_type: str | None
    doc_type_confidence: float | None
    language: str | None
    doc_date: date | None
    author_party: str | None
    status: str
    page_count: int
    extraction_method: str | None
    ocr_pages: int
    error: str | None
    security_flags: list[dict]
    meta: dict
    is_demo: bool
    created_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    doc_type: str | None = Field(default=None, max_length=40)
    doc_date: date | None = None
    author_party: Literal["contractor", "employer", "engineer", "subcontractor", "other"] | None = None


class ClauseOut(ORM):
    id: str
    document_id: str
    clause_number: str
    title: str
    parent_title: str | None
    text: str
    language: str
    page_start: int
    page_end: int
    page_is_estimated: bool
    category: str
    secondary_categories: list[str]
    obligations: list[str]
    entitlements: list[str]
    conditions: list[str]
    time_limits: list[dict]
    exclusions: list[str]
    percentages: list[dict]
    risk_flags: list[dict]
    confidence: float
    extraction_method: str
    verification_status: str
    verified_by: str | None
    verified_at: datetime | None
    reviewer_note: str | None


class ClauseVerifyIn(BaseModel):
    status: Literal["verified", "rejected", "corrected", "unverified"]
    category: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=4000)
    time_limits: list[dict] | None = None


# ---------------------------------------------------------------- events


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=20000)
    event_date: date
    awareness_date: date | None = None
    category: str | None = None
    responsible_party: Literal["employer", "engineer", "contractor", "subcontractor", "third_party", "neutral"] | None = None
    impacted_activities: list[str] = Field(default_factory=list, max_length=50)
    est_cost_impact: Decimal | None = Field(default=None, ge=0, le=Decimal("1e13"))
    est_time_impact_days: int | None = Field(default=None, ge=0, le=3650)
    currency: str = Field(default="EGP", pattern=r"^[A-Z]{3}$")
    reviewer_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in EVENT_CATEGORIES:
            raise ValueError("Unknown event category")
        return v


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    event_date: date | None = None
    awareness_date: date | None = None
    category: str | None = None
    responsible_party: str | None = None
    impacted_activities: list[str] | None = None
    est_cost_impact: Decimal | None = Field(default=None, ge=0)
    est_time_impact_days: int | None = Field(default=None, ge=0, le=3650)
    status: Literal["open", "under_review", "closed"] | None = None
    reviewer_id: str | None = None

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in EVENT_CATEGORIES:
            raise ValueError("Unknown event category")
        return v


class EventOut(ORM):
    id: str
    project_id: str
    ref: str
    title: str
    description: str
    event_date: date
    awareness_date: date | None
    category: str
    category_source: str
    suggested_category: str | None
    suggested_category_confidence: float | None
    responsible_party: str | None
    impacted_activities: list[str]
    est_cost_impact: Decimal | None
    est_time_impact_days: int | None
    currency: str
    status: str
    reviewer_id: str | None
    is_demo: bool
    created_at: datetime


class LinkDocIn(BaseModel):
    document_id: str
    confirmed: bool = True


class ClassifyIn(BaseModel):
    text: str = Field(min_length=3, max_length=20000)


# ---------------------------------------------------------------- entitlements & valuation


class EntitlementOut(ORM):
    id: str
    project_id: str
    event_id: str
    ref: str
    entitlement_type: str
    title: str
    status: str
    primary_clause_id: str | None
    related_clause_ids: list[str]
    conditions: list[dict]
    evidence_available: list[dict]
    evidence_missing: list[dict]
    evidence_completeness: float
    financial_impact: Decimal | None
    financial_basis: str
    currency: str
    time_impact_days: int | None
    notice: dict
    exclusions: list[dict]
    risk_level: str
    risk_factors: list[dict]
    confidence: float
    confidence_breakdown: dict
    explanation: list[dict]
    facts: list[dict]
    assumptions: list[dict]
    narrative: dict | None
    recommended_actions: list[dict]
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_comment: str | None
    engine_version: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class ReviewIn(BaseModel):
    decision: Literal["accepted", "rejected", "needs_info", "substantiated"]
    comment: str = Field(min_length=3, max_length=4000)


class ValuationLineIn(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=2000)
    quantity: Decimal = Field(ge=0, le=Decimal("1e12"))
    unit: str | None = Field(default=None, max_length=30)
    rate: Decimal = Field(ge=0, le=Decimal("1e12"))
    source_document_id: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_note: str | None = Field(default=None, max_length=1000)
    rate_basis: Literal["boq_rate", "invoice", "user_input", "estimate", "new_rate"] = "user_input"

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in COST_CATEGORIES:
            raise ValueError("Unknown cost category")
        return v


class ValuationIn(BaseModel):
    currency: str = Field(default="EGP", pattern=r"^[A-Z]{3}$")
    fx_rate_to_egp: Decimal = Field(default=Decimal(1), gt=0, le=Decimal(100000))
    overhead_pct: Decimal = Field(default=Decimal(0), ge=0, le=100)
    profit_pct: Decimal = Field(default=Decimal(0), ge=0, le=100)
    vat_applicable: bool = False
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    contractual_basis_note: str | None = Field(default=None, max_length=4000)
    lines: list[ValuationLineIn] = Field(max_length=500)


# ---------------------------------------------------------------- claims


class ClaimIn(BaseModel):
    entitlement_id: str
    title: str | None = Field(default=None, max_length=300)
    owner_id: str | None = None
    notes: str | None = Field(default=None, max_length=10000)


class ClaimOut(ORM):
    id: str
    project_id: str
    entitlement_id: str | None
    ref: str
    title: str
    claim_type: str
    stage: str
    claimed_amount: Decimal
    approved_amount: Decimal
    collected_amount: Decimal
    currency: str
    eot_claimed_days: int | None
    eot_approved_days: int | None
    submitted_at: date | None
    responded_at: date | None
    closed_at: date | None
    owner_id: str | None
    notes: str | None
    is_demo: bool
    created_at: datetime


class TransitionIn(BaseModel):
    to_stage: str
    comment: str | None = Field(default=None, max_length=4000)
    approved_amount: Decimal | None = Field(default=None, ge=0)
    collected_amount: Decimal | None = Field(default=None, ge=0)
    eot_approved_days: int | None = Field(default=None, ge=0)
    on_date: date | None = None


class GenerateIn(BaseModel):
    kind: Literal["notice", "package", "worksheet"]
    fmt: Literal["docx", "pdf", "xlsx"]
    language: Lang = "en"


# ---------------------------------------------------------------- deadlines


class DeadlineOut(ORM):
    id: str
    project_id: str
    entitlement_id: str | None
    claim_id: str | None
    clause_id: str | None
    event_id: str | None
    title: str
    deadline_type: str
    trigger_date: date | None
    trigger_description: str | None
    period_days: int | None
    day_type: str | None
    due_date: date | None
    certainty: str
    uncertainty_notes: list[dict]
    calculation: dict
    status: str
    assigned_to: str | None
    escalation_level: int
    completed_at: datetime | None
    is_demo: bool


class DeadlineIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    deadline_type: Literal["notice", "detailed_claim", "response", "payment", "milestone", "retention", "other"]
    due_date: date | None = None
    trigger_date: date | None = None
    period_days: int | None = Field(default=None, ge=0, le=3650)
    day_type: Literal["calendar", "working", "unspecified"] | None = None
    assigned_to: str | None = None
    clause_id: str | None = None


class DeadlineUpdate(BaseModel):
    status: Literal["open", "completed", "waived"] | None = None
    assigned_to: str | None = None
    due_date: date | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    language: Lang = "en"


class Paged(BaseModel):
    items: list[Any]
    total: int
