"""Normalised domain model. Every analytical artefact is traceable to the dataset version,
model version, seed and controls that produced it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


def _id() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=uid)


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------- tenancy & identity
class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = _id()
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _ts()


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = _id()
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()
    roles: Mapped[list[Role]] = relationship(secondary="user_roles", lazy="selectin")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str] = mapped_column(String(100))
    name_ar: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[Permission]] = relationship(secondary="role_permissions", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = _id()
    key: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(String(300), default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


# ---------------------------------------------------------------- enterprise data
class EnterpriseDataset(Base):
    __tablename__ = "enterprise_datasets"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(40))  # synthetic | csv | excel | odoo
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()
    versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="dataset", order_by="DatasetVersion.version", lazy="selectin")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)
    id: Mapped[str] = _id()
    dataset_id: Mapped[str] = mapped_column(ForeignKey("enterprise_datasets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checksum: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()
    dataset: Mapped[EnterpriseDataset] = relationship(back_populates="versions")


class DataConnection(Base):
    __tablename__ = "data_connections"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # synthetic_erp | csv | excel | odoo | d365_fo | d365_bc | sap | rest | sql
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="not_configured")
    implementation: Mapped[str] = mapped_column(String(30), default="interface_only")  # working | adapter | interface_only
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # non-secret config only
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _ts()


# ---------------------------------------------------------------- decisions
class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60), default="opex_optimization")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    controls: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    intake: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recommended_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    objectives: Mapped[list[DecisionObjective]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    constraints: Mapped[list[DecisionConstraint]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class DecisionObjective(Base):
    __tablename__ = "decision_objectives"
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    description_en: Mapped[str] = mapped_column(String(400))
    description_ar: Mapped[str] = mapped_column(String(400))
    metric: Mapped[str] = mapped_column(String(80))
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)


class DecisionConstraint(Base):
    __tablename__ = "decision_constraints"
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    description_en: Mapped[str] = mapped_column(String(400))
    description_ar: Mapped[str] = mapped_column(String(400))
    kind: Mapped[str] = mapped_column(String(10), default="hard")
    metric: Mapped[str] = mapped_column(String(80))
    operator: Mapped[str] = mapped_column(String(4))
    threshold: Mapped[float] = mapped_column(Float)


class DecisionRun(Base):
    """One orchestrated multi-agent analysis of a decision."""

    __tablename__ = "decision_runs"
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed|cancelled
    mode: Mapped[str] = mapped_column(String(30), default="rule_based")  # rule_based | llm_augmented
    llm_provider: Mapped[str] = mapped_column(String(30), default="none")
    llm_model: Mapped[str] = mapped_column(String(80), default="")
    current_stage: Mapped[str] = mapped_column(String(50), default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    pacing_ms: Mapped[int] = mapped_column(Integer, default=0)
    compute_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # recommendation & dossier summary
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = _ts()
    stage: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(40))  # stage_started|stage_completed|agent_*|warning|error|retry|message
    agent_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message_en: Mapped[str] = mapped_column(Text, default="")
    message_ar: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ---------------------------------------------------------------- agents
class AgentDefinition(Base):
    __tablename__ = "agent_definitions"
    id: Mapped[str] = _id()
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(120))
    role_en: Mapped[str] = mapped_column(Text)
    role_ar: Mapped[str] = mapped_column(Text)
    authority: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id: Mapped[str] = _id()
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    agent_key: Mapped[str] = mapped_column(ForeignKey("agent_definitions.key"))
    phase: Mapped[str] = mapped_column(String(30))  # independent_analysis | court | risk | governance
    status: Mapped[str] = mapped_column(String(20), default="running")
    mode: Mapped[str] = mapped_column(String(30), default="rule_based")
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_narrative_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_narrative_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = _ts()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentFinding(Base):
    __tablename__ = "agent_findings"
    id: Mapped[str] = _id()
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("agent_executions.id", ondelete="CASCADE"))
    agent_key: Mapped[str] = mapped_column(String(40), index=True)
    phase: Mapped[str] = mapped_column(String(30))
    code: Mapped[str] = mapped_column(String(40))
    claim_type: Mapped[str] = mapped_column(String(20))  # fact|estimate|assumption|hypothesis|recommendation
    topic: Mapped[str] = mapped_column(String(60))
    strategy_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stance: Mapped[str] = mapped_column(String(20), default="neutral")  # support|oppose|conditional|neutral
    text_en: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_quality: Mapped[float] = mapped_column(Float, default=0.5)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[list[EvidenceRecord]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[str] = _id()
    finding_id: Mapped[str] = mapped_column(ForeignKey("agent_findings.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(30))  # dataset|simulation|validation|des|policy|assumption
    reference: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentObjection(Base):
    __tablename__ = "agent_objections"
    id: Mapped[str] = _id()
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    raised_by: Mapped[str] = mapped_column(String(40))
    target_agent: Mapped[str] = mapped_column(String(40))
    target_finding_id: Mapped[str | None] = mapped_column(ForeignKey("agent_findings.id", ondelete="SET NULL"), nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    objection_type: Mapped[str] = mapped_column(String(40))  # unsupported_assumption|contradiction|optimism|dependency|policy
    severity: Mapped[str] = mapped_column(String(10))
    text_en: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[str] = mapped_column(Text)
    response_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    response_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str] = mapped_column(String(20), default="unresolved")  # resolved|partially|unresolved
    seq: Mapped[int] = mapped_column(Integer, default=0)


class DecisionCollision(Base):
    __tablename__ = "decision_collisions"
    id: Mapped[str] = _id()
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(20))
    strategy_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    severity: Mapped[str] = mapped_column(String(10))
    severity_score: Mapped[float] = mapped_column(Float)
    title_en: Mapped[str] = mapped_column(String(300))
    title_ar: Mapped[str] = mapped_column(String(300))
    positions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    affected_objectives: Mapped[list[str]] = mapped_column(JSON, default=list)
    consequences: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    resolutions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- scenarios & simulation
class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), nullable=True)
    key: Mapped[str] = mapped_column(String(20))
    name_en: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200))
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = _ts()


class SimulationModel(Base):
    __tablename__ = "simulation_models"
    __table_args__ = (UniqueConstraint("key", "version"),)
    id: Mapped[str] = _id()
    key: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    economics: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="production")  # production | candidate | retired
    created_at: Mapped[datetime] = _ts()


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), nullable=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("simulation_models.id"))
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    kind: Mapped[str] = mapped_column(String(20), default="pipeline")  # pipeline | what_if
    controls: Mapped[dict[str, Any]] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    iterations: Mapped[int] = mapped_column(Integer)
    input_fingerprint: Mapped[str] = mapped_column(String(32), index=True)
    elapsed_ms: Mapped[float] = mapped_column(Float)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()
    results: Mapped[list[SimulationResult]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SimulationResult(Base):
    __tablename__ = "simulation_results"
    id: Mapped[str] = _id()
    simulation_run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[str] = _id()
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(20))
    risk_code: Mapped[str] = mapped_column(String(30))
    title_en: Mapped[str] = mapped_column(String(300))
    title_ar: Mapped[str] = mapped_column(String(300))
    probability: Mapped[float] = mapped_column(Float)
    impact_egp_m: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10))
    basis: Mapped[str] = mapped_column(String(300))
    mitigation_en: Mapped[str] = mapped_column(Text)
    mitigation_ar: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------- governance
class GovernancePolicy(Base):
    __tablename__ = "governance_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name_en: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200))
    description_en: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[str] = mapped_column(Text)
    effect: Mapped[str] = mapped_column(String(20))  # deny | require_approval | require_acknowledgement
    rule: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)  # non-negotiable policies cannot be disabled
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class GovernanceEvaluation(Base):
    __tablename__ = "governance_evaluations"
    id: Mapped[str] = _id()
    run_id: Mapped[str | None] = mapped_column(ForeignKey("decision_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), nullable=True)
    scenario_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(30))  # allowed | requires_approval | denied
    required_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = _ts()


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("decision_runs.id", ondelete="SET NULL"), nullable=True)
    scenario_key: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|needs_analysis|blocked
    required_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    justification: Mapped[str] = mapped_column(Text, default="")
    governance_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()
    decisions: Mapped[list[ApprovalDecision]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[str] = _id()
    request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role_key: Mapped[str] = mapped_column(String(50))
    verdict: Mapped[str] = mapped_column(String(20))  # approve | reject | request_analysis
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _ts()


# ---------------------------------------------------------------- automation
class AutomationWorkflow(Base):
    __tablename__ = "automation_workflows"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)
    id: Mapped[str] = _id()
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    name_en: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200))
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ar: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(40))  # schedule | webhook | event | manual
    schedule: Mapped[str | None] = mapped_column(String(60), nullable=True)
    consequential: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(20), default="dry_run")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    n8n_webhook_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retry_max: Mapped[int] = mapped_column(Integer, default=3)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    id: Mapped[str] = _id()
    workflow_id: Mapped[str] = mapped_column(ForeignKey("automation_workflows.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(20))  # dry_run_ok|queued|delivered|failed|blocked
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    triggered_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()


# ---------------------------------------------------------------- audit & feedback loop
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(10))  # user | agent | system
    actor_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64))
    ts: Mapped[datetime] = _ts()


class ActualOutcome(Base):
    __tablename__ = "actual_outcomes"
    __table_args__ = (UniqueConstraint("decision_id", "month", "metric"),)
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    month: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(60))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _ts()


class ForecastComparison(Base):
    __tablename__ = "forecast_comparisons"
    id: Mapped[str] = _id()
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    simulation_run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"))
    scenario_key: Mapped[str] = mapped_column(String(20))
    month: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(60))
    predicted: Mapped[float] = mapped_column(Float)
    predicted_p10: Mapped[float] = mapped_column(Float)
    predicted_p90: Mapped[float] = mapped_column(Float)
    actual: Mapped[float] = mapped_column(Float)
    error: Mapped[float] = mapped_column(Float)
    error_pct: Mapped[float] = mapped_column(Float)
    within_interval: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _ts()
