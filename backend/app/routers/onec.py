import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.folder import Folder
from app.models.onec import OneCRecord
from app.models.user import User
from app.services import onec_import_service
from app.services.onec_import_service import OneCImportError
from app.services.onec_service import ENTITIES, ODataReader, OneCError, OneCBusy, reference_status, sync_references

router = APIRouter(prefix="/api/integrations/1c", tags=["1c"], dependencies=[Depends(require_permission("admin.manage"))])


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    try:
        return await reference_status(db)
    except OneCError as exc:
        raise HTTPException(503, detail=str(exc)) from None


@router.post("/sync")
async def sync(db: AsyncSession = Depends(get_db)):
    try:
        return await sync_references(db)
    except OneCBusy as exc:
        raise HTTPException(409, detail=str(exc)) from None
    except OneCError as exc:
        raise HTTPException(503, detail=str(exc)) from None


@router.get("/records/{kind}")
async def records(kind: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    if kind not in ENTITIES:
        raise HTTPException(404, detail="unknown_1c_reference")
    try:
        reader = ODataReader()
    except OneCError as exc:
        raise HTTPException(503, detail=str(exc)) from None
    conditions = (OneCRecord.source == reader.source, OneCRecord.entity == kind)
    total = (await db.execute(select(func.count()).select_from(OneCRecord).where(*conditions))).scalar()
    rows = (await db.execute(select(OneCRecord).where(*conditions).order_by(OneCRecord.ref).offset(offset).limit(limit))).scalars().all()
    return {"total": total, "offset": offset, "limit": limit, "items": [r.data for r in rows]}


class ImportRequest(BaseModel):
    workshop_id: uuid.UUID
    dry_run: bool = True


@router.get("/import/workshops")
async def import_workshops(db: AsyncSession = Depends(get_db)):
    folders = (await db.execute(select(Folder).where(Folder.parent_id.is_(None)).order_by(Folder.name))).scalars().all()
    return [{"id": folder.id, "name": folder.name} for folder in folders]


@router.post("/import")
async def import_recipes(payload: ImportRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        source = ODataReader().source
        return await onec_import_service.import_recipes(db, source, payload.workshop_id, user.id, dry_run=payload.dry_run)
    except OneCBusy as exc:
        raise HTTPException(409, detail=str(exc)) from None
    except OneCImportError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    except OneCError as exc:
        raise HTTPException(503, detail=str(exc)) from None
