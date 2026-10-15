from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..connectors.base import ConnectorError
from ..connectors.erp_adapters import REGISTRY
from ..connectors.file_import import import_profile
from ..connectors.synthetic import generate_gl, generate_projects
from ..db import get_db
from ..models import DataConnection, DatasetVersion, EnterpriseDataset, User
from ..seed import checksum
from ..security import require
from ..services.audit import audit
from ..services.dossier import row
from ..simulation.assumptions import BASELINE_PROVENANCE, Baseline
from ..simulation.validation import validate_baseline

router = APIRouter(tags=["data"])
DB = Annotated[Session, Depends(get_db)]


def _ds(db: Session, user: User, dataset_id: str) -> EnterpriseDataset:
    ds = db.get(EnterpriseDataset, dataset_id)
    if not ds or ds.tenant_id != user.tenant_id:
        raise HTTPException(404, "Dataset not found")
    return ds


def _new_version(db: Session, ds: EnterpriseDataset, data: dict, provenance: dict, note: str, user: User) -> DatasetVersion:
    b = Baseline(**data)
    nxt = (db.scalar(select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id == ds.id)) or 0) + 1
    dv = DatasetVersion(dataset_id=ds.id, version=nxt, data=b.model_dump(), provenance=provenance,
                        validation=validate_baseline(b).model_dump(), checksum=checksum(b.model_dump()), note=note,
                        created_by=user.id)
    db.add(dv)
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="dataset.version_created",
          entity_type="dataset_version", entity_id=dv.id, detail={"version": nxt, "note": note})
    return dv


@router.get("/datasets")
def list_datasets(db: DB, user: Annotated[User, require("dataset.read")]) -> list[dict[str, Any]]:
    out = []
    for ds in db.scalars(select(EnterpriseDataset).where(EnterpriseDataset.tenant_id == user.tenant_id)):
        out.append({**row(ds), "versions": [row(v) for v in reversed(ds.versions)]})
    return out


class VersionIn(BaseModel):
    data: dict[str, Any]
    note: str = ""


@router.post("/datasets/{dataset_id}/versions", status_code=201)
def create_version(dataset_id: str, body: VersionIn, db: DB, user: Annotated[User, require("dataset.write")]) -> dict[str, Any]:
    ds = _ds(db, user, dataset_id)
    latest = ds.versions[-1]
    merged = {**latest.data, **body.data}
    try:
        Baseline(**merged)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Invalid dataset: {exc}") from exc
    prov = dict(latest.provenance)
    for k in body.data:
        if merged.get(k) != latest.data.get(k):
            prov[k] = "user_input"
    return row(_new_version(db, ds, merged, prov, body.note or "Edited assumptions", user))


@router.post("/datasets/validate")
def validate(body: dict[str, Any], user: Annotated[User, require("dataset.read")]) -> dict[str, Any]:
    try:
        return validate_baseline(Baseline(**body)).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, str(exc)) from exc


@router.post("/datasets/{dataset_id}/import", status_code=201)
async def import_file(dataset_id: str, db: DB, user: Annotated[User, require("dataset.write")],
                      file: UploadFile = File(...)) -> dict[str, Any]:
    ds = _ds(db, user, dataset_id)
    content = await file.read()
    try:
        res = import_profile(file.filename or "upload.csv", content, Baseline(**ds.versions[-1].data))
    except ConnectorError as exc:
        raise HTTPException(422, str(exc)) from exc
    prov = {k: ("imported" if res.profile.get(k) != ds.versions[-1].data.get(k) else v)
            for k, v in ds.versions[-1].provenance.items()}
    dv = _new_version(db, ds, res.profile, prov, f"Imported from {file.filename}", user)
    return {"version": row(dv), "reconciliation": res.reconciliation, "rows_read": res.rows_read}


@router.get("/datasets/synthetic/ledger")
def synthetic_ledger(user: Annotated[User, require("dataset.read")], seed: int = 42) -> dict[str, Any]:
    gl = generate_gl(seed=seed)
    return {"synthetic": True, "rows": gl, "projects": generate_projects(seed=seed)}


# ------------------------------------------------------------------ connectors
@router.get("/connectors")
def list_connectors(db: DB, user: Annotated[User, require("dataset.read")]) -> list[dict[str, Any]]:
    return [row(c) for c in db.scalars(select(DataConnection).where(DataConnection.tenant_id == user.tenant_id)
                                       .order_by(DataConnection.created_at))]


def _conn(db: Session, user: User, cid: str) -> DataConnection:
    c = db.get(DataConnection, cid)
    if not c or c.tenant_id != user.tenant_id:
        raise HTTPException(404, "Connection not found")
    return c


class ConnIn(BaseModel):
    config: dict[str, Any]


@router.patch("/connectors/{cid}")
def configure(cid: str, body: ConnIn, db: DB, user: Annotated[User, require("connector.manage")]) -> dict[str, Any]:
    c = _conn(db, user, cid)
    forbidden = {k for k in body.config if any(s in k.lower() for s in ("password", "secret", "token", "api_key"))}
    if forbidden:
        raise HTTPException(422, "Secrets must be provided via environment/secret store, not stored in config")
    c.config = {**c.config, **body.config}
    db.commit()
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="connector.configured",
          entity_type="data_connection", entity_id=c.id, detail={"keys": sorted(body.config)})
    return row(c)


@router.post("/connectors/{cid}/test")
def test_connector(cid: str, db: DB, user: Annotated[User, require("connector.manage")]) -> dict[str, Any]:
    c = _conn(db, user, cid)
    cls = REGISTRY.get(c.kind)
    if not cls:
        return {"ok": True, "message": "File-based import: upload via dataset import", "verified_live": False}
    import os
    res = cls(c.config, {"api_key": os.environ.get(f"FM_{c.kind.upper()}_API_KEY", "")}).test_connection()
    c.status = "connected" if res["ok"] else ("error" if c.implementation != "interface_only" else "not_configured")
    c.last_result = res
    db.commit()
    return res


@router.post("/connectors/{cid}/sync")
def sync_connector(cid: str, db: DB, user: Annotated[User, require("dataset.write")]) -> dict[str, Any]:
    c = _conn(db, user, cid)
    cls = REGISTRY.get(c.kind)
    if not cls:
        raise HTTPException(400, "Use dataset import for file connectors")
    ds = db.scalar(select(EnterpriseDataset).where(EnterpriseDataset.tenant_id == user.tenant_id)
                   .order_by(EnterpriseDataset.created_at))
    import os
    try:
        res = cls(c.config, {"api_key": os.environ.get(f"FM_{c.kind.upper()}_API_KEY", "")}).fetch_cost_profile(
            Baseline(**ds.versions[-1].data))
    except (ConnectorError, OSError) as exc:
        c.status, c.last_result = "error", {"ok": False, "message": str(exc)}
        db.commit()
        raise HTTPException(502, f"Connector sync failed: {exc}") from exc
    changed = {k for k, v in res.profile.items() if ds.versions[-1].data.get(k) != v}
    c.last_sync_at = datetime.now(UTC)
    c.last_result = {"ok": True, "rows_read": res.rows_read, "reconciliation": res.reconciliation,
                     "verified_live": res.verified_live, "changed_fields": sorted(changed)}
    db.commit()
    out = {"reconciliation": res.reconciliation, "rows_read": res.rows_read, "changed_fields": sorted(changed),
           "verified_live": res.verified_live}
    if changed:
        prov = {k: ("imported" if k in changed else v) for k, v in (ds.versions[-1].provenance or BASELINE_PROVENANCE).items()}
        out["version"] = row(_new_version(db, ds, res.profile, prov, f"Synced from {c.name}", user))
    audit(db, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, action="connector.synced",
          entity_type="data_connection", entity_id=c.id, detail={"rows": res.rows_read, "changed": sorted(changed)})
    return out
