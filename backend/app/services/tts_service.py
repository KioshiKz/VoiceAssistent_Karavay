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
SPEAKER = "aidar"

_model = None
_model_lock = threading.Lock()


class TTSUnavailableError(RuntimeError):
    """Raised when the optional server-side speech engine cannot be used."""


def _import_torch():
    try:
        import torch
    except (ImportError, OSError) as exc:
        raise TTSUnavailableError(
            "Silero TTS requires the optional CPU-only torch dependency"
        ) from exc
    return torch


_ONES = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = [
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]

# Genitive forms, needed for prepositions that govern the genitive case
# ("из пяти", "до десяти", "для трёх") — Silero has no case-agreement of its
# own, so the correct form has to be picked before synthesis.
_ONES_GEN = ["", "одного", "двух", "трёх", "четырёх", "пяти", "шести", "семи", "восьми", "девяти"]
_TEENS_GEN = [
    "десяти", "одиннадцати", "двенадцати", "тринадцати", "четырнадцати", "пятнадцати",
    "шестнадцати", "семнадцати", "восемнадцати", "девятнадцати",
]
_TENS_GEN = ["", "", "двадцати", "тридцати", "сорока", "пятидесяти", "шестидесяти", "семидесяти", "восьмидесяти", "девяноста"]
_HUNDREDS_GEN = ["", "ста", "двухсот", "трёхсот", "четырёхсот", "пятисот", "шестисот", "семисот", "восьмисот", "девятисот"]


def _three_digits_to_words(n: int, feminine: bool = False, case: str = "nom") -> list[str]:
    ones, teens, tens, hundreds_table = (
        (_ONES_GEN, _TEENS_GEN, _TENS_GEN, _HUNDREDS_GEN) if case == "gen" else (_ONES, _TEENS, _TENS, _HUNDREDS)
    )
    words = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        words.append(hundreds_table[hundreds])
    if 10 <= rest < 20:
        words.append(teens[rest - 10])
    else:
        tens_digit, ones_digit = divmod(rest, 10)
        if tens_digit:
            words.append(tens[tens_digit])
        if ones_digit:
            word = ones[ones_digit]
            if feminine and case == "nom":
                word = {"один": "одна", "два": "две"}.get(word, word)
            elif feminine and case == "gen" and ones_digit == 1:
                word = "одной"
            words.append(word)
    return words


def number_to_words_ru(n: int, feminine: bool = False, case: str = "nom") -> str:
    """Silero TTS reads digit runs unreliably (skips or mispronounces them), so
    numbers are spelled out in Russian before synthesis instead. `feminine`
    agrees "один/два" as "одна/две" for feminine nouns (e.g. "одна минута").
    `case` selects "nom" (default) or "gen", for genitive-governing
    prepositions such as "из"/"до"/"для"/"без"/"от"/"с"."""
    if n == 0:
        return "нуля" if case == "gen" else "ноль"
    if n > 999_999:
        return str(n)

    parts: list[str] = []
    thousands, rest = divmod(n, 1000)
    if thousands:
        if thousands == 1:
            parts.append("тысячи" if case == "gen" else "тысяча")
        elif 2 <= thousands <= 4:
            # "тысяча" is itself feminine, regardless of the trailing noun's gender.
            words = _three_digits_to_words(thousands, feminine=True, case=case)
            parts.extend(words)
            parts.append("тысяч" if case == "gen" else "тысячи")
        else:
            parts.extend(_three_digits_to_words(thousands, case=case))
            parts.append("тысяч")
    parts.extend(_three_digits_to_words(rest, feminine=feminine, case=case))
    return " ".join(parts) if parts else ("нуля" if case == "gen" else "ноль")


# Prepositions that govern the genitive case when followed by a number
# ("Шаг 2 из 5" -> "из пяти", not "из пять").
_GENITIVE_PREPOSITIONS = {"из", "до", "для", "без", "от", "с", "около", "более", "менее", "кроме"}
# Captures an optional governing word immediately before a number, so callers
# can pick the number's grammatical case from it.
_PREP_PREFIX = r"(?:([а-яА-ЯёЁ]+)(\s+))?"


def _case_for(preposition: str | None) -> str:
    return "gen" if (preposition or "").lower() in _GENITIVE_PREPOSITIONS else "nom"


def _expand_numbers(text: str) -> str:
    def repl(match: re.Match) -> str:
        preposition, gap, digits = match.group(1), match.group(2), match.group(3)
        words = number_to_words_ru(int(digits), case=_case_for(preposition))
        return f"{preposition}{gap}{words}" if preposition else words

    return re.sub(rf"{_PREP_PREFIX}(\d+)", repl, text)


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


def _plural_ru(number_text: str, forms: tuple[str, str, str], case: str = "nom") -> str:
    """Picks the (one, few, many) noun form. Under a genitive-governing
    preposition ("без пяти минут") the noun is always genitive: singular
    (the "few" slot, e.g. "минуты") for a trailing 1, plural (the "many"
    slot, e.g. "минут") otherwise — unlike the nominative-counting rule
    where 2-4 also gets the "few" slot."""
    one, few, many = forms
    if "." in number_text or "," in number_text:
        return few
    n = int(number_text)
    is_one = n % 10 == 1 and n % 100 != 11
    if case == "gen":
        return few if is_one else many
    if 11 <= n % 100 <= 14:
        return many
    if is_one:
        return one
    last_digit = n % 10
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
        preposition, gap, number = match.group(1), match.group(2), match.group(3)
        case = _case_for(preposition)
        forms = _UNIT_FORMS[unit_key]
        word = _plural_ru(number, forms, case=case)
        feminine = unit_key in _FEMININE_UNIT_KEYS
        if (feminine or case == "gen") and "." not in number and "," not in number:
            number = number_to_words_ru(int(number), feminine=feminine, case=case)
        prefix = f"{preposition}{gap}" if preposition else ""
        return f"{prefix}{number} {word}"

    text = re.sub(rf"{_PREP_PREFIX}(\d+(?:[.,]\d+)?)\s*°\s*[CС]\b", lambda m: repl(m, "°c"), text)
    text = re.sub(
        rf"{_PREP_PREFIX}(\d+(?:[.,]\d+)?)\s*(кг|мл|мин|сек|шт|л|г|ч)\b",
        lambda m: repl(m, m.group(4).lower()),
        text,
    )
    return text


def ensure_model_file() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists():
        torch = _import_torch()
        torch.hub.download_url_to_file(MODEL_URL, str(MODEL_PATH))
    return MODEL_PATH


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        torch = _import_torch()
        torch.set_num_threads(4)
        model_path = ensure_model_file()
        # PyTorch's Windows file reader cannot open non-ASCII paths reliably
        # (the project is commonly installed below a Cyrillic directory).
        # Loading through a binary buffer keeps model discovery Unicode-safe.
        model_buffer = io.BytesIO(model_path.read_bytes())
        model = torch.package.PackageImporter(model_buffer).load_pickle("tts_models", "model")
        model.to(torch.device("cpu"))
        _model = model
        return _model


def _synthesize_sync(text: str) -> bytes:
    torch = _import_torch()
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
    try:
        return await asyncio.to_thread(_synthesize_sync, spoken_text)
    except TTSUnavailableError:
        raise
    except Exception as exc:
        raise TTSUnavailableError("Silero TTS synthesis failed") from exc
