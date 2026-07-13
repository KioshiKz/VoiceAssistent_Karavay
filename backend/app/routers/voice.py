from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.event_template import EventTemplate
from app.models.ingredient import Ingredient
from app.models.order import OrderLine
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.models.user import User
from app.services import tts_service

router = APIRouter(prefix="/api/voice", tags=["voice"])
VOICE_EVENT_LIMIT = 200
VOICE_EVENTS: list[dict[str, object]] = []
VOICE_EVENT_COUNTER = int(datetime.now(timezone.utc).timestamp() * 1000)

COMMAND_PHRASES = [
    "помощник",
    "асистент",
    "отмена",
    "остановить",
    "стоп",
    "открыть текущую заявку",
    "открыть заявку",
    "текущая заявка",
    "заявки",
    "дальше",
    "некст",
    "продолжить",
    "вернуться",
    "назад",
    "старт",
    "полный экран",
    "на полный экран",
    "следующая заявка",
    "следущая заявка",
    "предыдущая заявка",
    "заявка",
    "повтори",
    "повторить",
]


class VoiceTranscriptIn(BaseModel):
    text: str = Field(min_length=1)
    source: str = "vosk"


class VoiceSpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class VoiceEventOut(BaseModel):
    id: int
    text: str
    source: str
    created_at: datetime


def _add_phrase(target: set[str], value: object) -> None:
    phrase = str(value or "").strip().lower()
    if phrase:
        target.add(phrase)


@router.get("/grammar")
async def voice_grammar(db: AsyncSession = Depends(get_db)):
    phrases: set[str] = set(COMMAND_PHRASES)

    for model in (Product, Ingredient, EventTemplate):
        result = await db.execute(select(model.name).where(model.is_active.is_(True)))
        for (name,) in result.all():
            _add_phrase(phrases, name)

    order_lines_result = await db.execute(
        select(OrderLine.product_name_raw, OrderLine.quantity, OrderLine.due_time)
        .where(OrderLine.status != "cancelled")
        .order_by(OrderLine.created_at.desc())
        .limit(300)
    )
    for product_name, quantity, due_time in order_lines_result.all():
        _add_phrase(phrases, product_name)
        _add_phrase(phrases, f"заявка {product_name}")
        _add_phrase(phrases, f"заявка {product_name} {quantity}")
        _add_phrase(phrases, f"заявка {due_time:%H %M}")
        _add_phrase(phrases, f"заявка {due_time:%H:%M}")
        # Combined "продукт + время" phrase, mirroring the "продукт + количество"
        # one above — without it the offline Vosk grammar never saw this exact
        # word sequence for any real order line.
        _add_phrase(phrases, f"заявка {product_name} {due_time:%H %M}")
        _add_phrase(phrases, f"заявка {product_name} {due_time:%H:%M}")

    steps_result = await db.execute(select(RecipeStep.event_params).where(RecipeStep.event_params.is_not(None)))
    for (params,) in steps_result.all():
        if not isinstance(params, dict):
            continue
        _add_phrase(phrases, params.get("phrase"))
        _add_phrase(phrases, params.get("start_phrase"))
        if "duration_seconds" in params:
            _add_phrase(phrases, "старт")

    return {
        "phrases": sorted(phrases),
        "commands": COMMAND_PHRASES,
    }


@router.post("/transcript", response_model=VoiceEventOut)
async def push_voice_transcript(payload: VoiceTranscriptIn):
    global VOICE_EVENT_COUNTER

    text = payload.text.strip().lower()
    if not text:
        raise HTTPException(status_code=400, detail="Voice transcript is empty")

    source = payload.source.strip() or "vosk"
    VOICE_EVENT_COUNTER += 1
    event = {
        "id": VOICE_EVENT_COUNTER,
        "text": text,
        "source": source,
        "created_at": datetime.now(timezone.utc),
    }
    VOICE_EVENTS.append(event)
    if len(VOICE_EVENTS) > VOICE_EVENT_LIMIT:
        del VOICE_EVENTS[: len(VOICE_EVENTS) - VOICE_EVENT_LIMIT]

    return event


@router.get("/events", response_model=list[VoiceEventOut])
async def voice_events(after: int = 0):
    return [event for event in VOICE_EVENTS if int(event["id"]) > after]


@router.post("/speak")
async def speak(payload: VoiceSpeakIn, user: User = Depends(get_current_user)):
    if not user.voice_assistant_enabled:
        raise HTTPException(status_code=409, detail="voice_assistant_disabled")
    try:
        wav_bytes = await tts_service.synthesize(payload.text)
    except tts_service.TTSUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "server_tts_unavailable",
                "message": "Серверный синтез речи недоступен. Используйте голос браузера.",
            },
        ) from exc
    return Response(content=wav_bytes, media_type="audio/wav")
