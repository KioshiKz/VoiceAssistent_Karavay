"""Offline Russian speech synthesis via Silero TTS (v4, single-file torch.package model).

The model weights (~50MB) are not committed to git — they are downloaded once into
MODEL_DIR on first use (see download script at backend/scripts/download_tts_model.py
for an explicit prefetch). This mirrors the existing offline-first approach used by
the Vosk speech-recognition script, but keeps the binary out of the repository this
time to avoid bloating it and the Docker build (see docs note on the Vosk model).
"""
import asyncio
import io
import re
import threading
import wave
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[2] / ".models" / "silero_tts"
MODEL_PATH = MODEL_DIR / "v4_ru.pt"
MODEL_URL = "https://models.silero.ai/models/tts/ru/v4_ru.pt"
SAMPLE_RATE = 48000
SPEAKER = "baya"

_model = None
_model_lock = threading.Lock()

_ONES = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = [
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _three_digits_to_words(n: int, feminine: bool = False) -> list[str]:
    words = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    if 10 <= rest < 20:
        words.append(_TEENS[rest - 10])
    else:
        tens, ones = divmod(rest, 10)
        if tens:
            words.append(_TENS[tens])
        if ones:
            word = _ONES[ones]
            if feminine:
                word = {"один": "одна", "два": "две"}.get(word, word)
            words.append(word)
    return words


def number_to_words_ru(n: int, feminine: bool = False) -> str:
    """Silero TTS reads digit runs unreliably (skips or mispronounces them), so
    numbers are spelled out in Russian before synthesis instead. `feminine`
    agrees "один/два" as "одна/две" for feminine nouns (e.g. "одна минута")."""
    if n == 0:
        return "ноль"
    if n > 999_999:
        return str(n)

    parts: list[str] = []
    thousands, rest = divmod(n, 1000)
    if thousands:
        if thousands == 1:
            parts.append("тысяча")
        elif 2 <= thousands <= 4:
            # "тысяча" is itself feminine, regardless of the trailing noun's gender.
            words = _three_digits_to_words(thousands, feminine=True)
            parts.extend(words)
            parts.append("тысячи")
        else:
            parts.extend(_three_digits_to_words(thousands))
            parts.append("тысяч")
    parts.extend(_three_digits_to_words(rest, feminine=feminine))
    return " ".join(parts) if parts else "ноль"


def _expand_numbers(text: str) -> str:
    return re.sub(r"\d+", lambda match: number_to_words_ru(int(match.group(0))), text)


# (one, few, many) as in "1 килограмм" / "3 килограмма" / "5 килограммов".
_UNIT_FORMS: dict[str, tuple[str, str, str]] = {
    "кг": ("килограмм", "килограмма", "килограммов"),
    "г": ("грамм", "грамма", "граммов"),
    "л": ("литр", "литра", "литров"),
    "мл": ("миллилитр", "миллилитра", "миллилитров"),
    "ч": ("час", "часа", "часов"),
    "мин": ("минута", "минуты", "минут"),
    "сек": ("секунда", "секунды", "секунд"),
    "шт": ("штука", "штуки", "штук"),
    "°c": ("градус", "градуса", "градусов"),
}


def _plural_ru(number_text: str, forms: tuple[str, str, str]) -> str:
    one, few, many = forms
    if "." in number_text or "," in number_text:
        return few
    n = int(number_text)
    if 11 <= n % 100 <= 14:
        return many
    last_digit = n % 10
    if last_digit == 1:
        return one
    if 2 <= last_digit <= 4:
        return few
    return many


# мин/сек/шт are feminine nouns ("одна минута", "две штуки"); the rest are
# masculine, so plain digits ("1"/"2") already read correctly as "один"/"два".
_FEMININE_UNIT_KEYS = {"мин", "сек", "шт"}


def _expand_units(text: str) -> str:
    """Units are abbreviated ("4 кг 0 г") in ingredient/timer display strings,
    but Silero reads abbreviations poorly, so spell them out with correct
    Russian plural agreement before synthesis."""

    def repl(match: re.Match, unit_key: str) -> str:
        number = match.group(1)
        forms = _UNIT_FORMS[unit_key]
        word = _plural_ru(number, forms)
        if unit_key in _FEMININE_UNIT_KEYS and "." not in number and "," not in number:
            number = number_to_words_ru(int(number), feminine=True)
        return f"{number} {word}"

    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*°\s*[CС]\b", lambda m: repl(m, "°c"), text)
    text = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(кг|мл|мин|сек|шт|л|г|ч)\b",
        lambda m: repl(m, m.group(2).lower()),
        text,
    )
    return text


def ensure_model_file() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists():
        import torch

        torch.hub.download_url_to_file(MODEL_URL, str(MODEL_PATH))
    return MODEL_PATH


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        import torch

        torch.set_num_threads(4)
        model_path = ensure_model_file()
        model = torch.package.PackageImporter(str(model_path)).load_pickle("tts_models", "model")
        model.to(torch.device("cpu"))
        _model = model
        return _model


def _synthesize_sync(text: str) -> bytes:
    import torch

    model = _load_model()
    audio = model.apply_tts(text=text, speaker=SPEAKER, sample_rate=SAMPLE_RATE, put_accent=True, put_yo=True)

    pcm16 = (audio.clamp(-1, 1) * 32767).to(dtype=torch.int16).numpy()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm16.tobytes())
    return buffer.getvalue()


async def synthesize(text: str) -> bytes:
    clean = text.strip()
    if not clean:
        raise ValueError("empty_text")
    spoken_text = _expand_numbers(_expand_units(clean))
    return await asyncio.to_thread(_synthesize_sync, spoken_text)
