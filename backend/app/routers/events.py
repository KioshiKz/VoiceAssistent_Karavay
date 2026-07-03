import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.event_template import EventTemplate
from app.models.recipe_step import RecipeStep
from app.models.user import User
from app.schemas.event_template import EventTemplateCreate, EventTemplateOut, EventTemplateUpdate
from app.services import folder_service, ingredient_service, permission_service

router = APIRouter(tags=["events"])


@router.get("/api/folders/{folder_id}/events", response_model=list[EventTemplateOut])
async def list_events(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.view", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    return await ingredient_service.visible_event_templates(db, folder)


@router.post("/api/folders/{folder_id}/events", response_model=EventTemplateOut, status_code=201)
async def create_event(
    folder_id: uuid.UUID,
    payload: EventTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    event = EventTemplate(folder_id=folder_id, **payload.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def _get_event_or_404(db: AsyncSession, event_id: uuid.UUID) -> EventTemplate:
    event = await db.get(EventTemplate, event_id)
    if event is None:
        raise HTTPException(404, detail="event_template_not_found")
    return event


@router.get("/api/events/{event_id}", response_model=EventTemplateOut)
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_event_or_404(db, event_id)


@router.patch("/api/events/{event_id}", response_model=EventTemplateOut)
async def update_event(
    event_id: uuid.UUID,
    payload: EventTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = await _get_event_or_404(db, event_id)
    folder = await folder_service.get_folder_or_404(db, event.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.edit", folder):
        raise HTTPException(403, detail="permission_denied")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/api/events/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = await _get_event_or_404(db, event_id)
    folder = await folder_service.get_folder_or_404(db, event.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.edit", folder):
        raise HTTPException(403, detail="permission_denied")

    referenced = await db.execute(select(RecipeStep.id).where(RecipeStep.event_template_id == event_id))
    if referenced.first() is not None:
        raise HTTPException(409, detail="event_template_referenced_by_recipe_steps")

    await db.delete(event)
    await db.commit()
