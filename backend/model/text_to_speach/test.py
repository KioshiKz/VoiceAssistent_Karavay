import json
import os
import queue
import sys
import time
import urllib.request
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel


SAMPLE_RATE = 16_000
BLOCK_SIZE = 4_000
CHANNELS = 1
NUMERAL_MAX = 9_999

audio_queue: queue.Queue[bytes] = queue.Queue()
last_partial_len = 0

COMMAND_PHRASES = [
    "помощник",
    "ограничение",
    "напиши много видов хлеба",
    "напиши виды хлеба",
    "много видов хлеба",
    "стоп",
    "прекрати",
    "пауза",
    "начать",
    "дальше",
]

BREAD_PHRASES = [
    "хлеб",
    "белый хлеб",
    "черный хлеб",
    "серый хлеб",
    "ржаной хлеб",
    "пшеничный хлеб",
    "ржано пшеничный хлеб",
    "цельнозерновой хлеб",
    "мультизлаковый хлеб",
    "зерновой хлеб",
    "хлеб с отрубями",
    "хлеб с семечками",
    "хлеб с орехами",
    "хлеб с изюмом",
    "бездрожжевой хлеб",
    "дрожжевой хлеб",
    "заквасочный хлеб",
    "заварной хлеб",
    "солодовый хлеб",
    "бородинский хлеб",
    "дарницкий хлеб",
    "нарезной хлеб",
    "формовой хлеб",
    "подовый хлеб",
    "тостовый хлеб",
    "крестьянский хлеб",
    "деревенский хлеб",
    "монастырский хлеб",
    "горчичный хлеб",
    "картофельный хлеб",
    "овсяный хлеб",
    "гречневый хлеб",
    "кукурузный хлеб",
    "рисовый хлеб",
    "льняной хлеб",
    "полбяной хлеб",
    "спельтовый хлеб",
    "амарантовый хлеб",
    "чесночный хлеб",
    "сырный хлеб",
    "луковый хлеб",
    "томатный хлеб",
    "тыквенный хлеб",
    "морковный хлеб",
    "сдобный хлеб",
    "сладкий хлеб",
    "французский хлеб",
    "итальянский хлеб",
    "грузинский хлеб",
    "армянский хлеб",
    "узбекский хлеб",
    "батон",
    "багет",
    "чиабатта",
    "фокачча",
    "лаваш",
    "пита",
    "наан",
    "маца",
    "тортилья",
    "бриошь",
    "бейгл",
    "лепешка",
    "каравай",
    "калач",
    "сайка",
    "плетенка",
    "булка",
    "булочка",
    "хала",
    "матнакаш",
    "шоти",
    "тандырный хлеб",
]

COMMAND_PHRASES = [
    "помощник",
    "отмена",
    "открыть текущую заявку",
    "дальше",
    "вернуться",
    "назад",
    "старт",
    "полный экран",
    "на полный экран",
]

BREAD_PHRASES = [
    "хлеб",
    "батон",
    "каравай",
    "ингредиент",
    "событие",
    "заявка",
    "таймер",
]

DEFAULT_VOICE_BASE_URL = os.environ.get("VOICE_BASE_URL", "http://127.0.0.1:8000/api/voice")
VOICE_GRAMMAR_URL = os.environ.get("VOICE_GRAMMAR_URL", f"{DEFAULT_VOICE_BASE_URL}/grammar")
VOICE_TRANSCRIPT_URL = os.environ.get("VOICE_TRANSCRIPT_URL", f"{DEFAULT_VOICE_BASE_URL}/transcript")

UNITS = {
    "masculine": [
        "",
        "один",
        "два",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ],
    "feminine": [
        "",
        "одна",
        "две",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ],
}

TEENS = [
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
]

TENS = [
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
]

HUNDREDS = [
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
]


def find_model_path() -> Path:
    env_path = os.getenv("VOSK_MODEL_PATH")
    if env_path:
        return Path(env_path).expanduser()

    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)

    candidates = [
        Path("vosk-model-small-ru-0.22"),
        Path("vosk-model-ru-0.42"),
        Path("model"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    ru_models = sorted(Path.cwd().glob("vosk-model*ru*"))
    if ru_models:
        return ru_models[0]

    raise FileNotFoundError(
        "Russian Vosk model was not found. Put the model folder next to "
        "test.py or set VOSK_MODEL_PATH."
    )


def under_thousand_to_words(number: int, gender: str = "masculine") -> str:
    if not 0 <= number < 1000:
        raise ValueError("number must be in range 0..999")

    parts = []
    hundreds = number // 100
    remainder = number % 100

    if hundreds:
        parts.append(HUNDREDS[hundreds])

    if 10 <= remainder <= 19:
        parts.append(TEENS[remainder - 10])
    else:
        tens = remainder // 10
        units = remainder % 10

        if tens:
            parts.append(TENS[tens])
        if units:
            parts.append(UNITS[gender][units])

    return " ".join(parts)


def thousand_form(number: int) -> str:
    if 10 <= number % 100 <= 19:
        return "тысяч"
    if number % 10 == 1:
        return "тысяча"
    if 2 <= number % 10 <= 4:
        return "тысячи"
    return "тысяч"


def number_to_words(number: int) -> str:
    if number == 0:
        return "ноль"
    if not 0 <= number <= NUMERAL_MAX:
        raise ValueError(f"number must be in range 0..{NUMERAL_MAX}")

    if number < 1000:
        return under_thousand_to_words(number)

    thousands = number // 1000
    remainder = number % 1000
    parts = [
        under_thousand_to_words(thousands, "feminine"),
        thousand_form(thousands),
    ]

    if remainder:
        parts.append(under_thousand_to_words(remainder))

    return " ".join(parts)


def load_backend_grammar() -> list[str]:
    print(f"[voice] Loading dynamic grammar: {VOICE_GRAMMAR_URL}", flush=True)
    try:
        with urllib.request.urlopen(VOICE_GRAMMAR_URL, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[voice] Backend grammar is unavailable, using local fallback: {exc}", file=sys.stderr, flush=True)
        return []

    phrases = payload.get("phrases", []) if isinstance(payload, dict) else []
    loaded = [str(phrase) for phrase in phrases if str(phrase).strip()]
    print(f"[voice] Dynamic grammar loaded: {len(loaded)} phrases", flush=True)
    return loaded


def post_transcript(text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return

    data = json.dumps({"text": cleaned, "source": "vosk"}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        VOICE_TRANSCRIPT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            response.read()
    except Exception as exc:
        print(f"[voice] Transcript relay failed: {exc}", file=sys.stderr, flush=True)


def build_grammar() -> list[str]:
    phrases = [
        *COMMAND_PHRASES,
        *BREAD_PHRASES,
        *load_backend_grammar(),
        *(number_to_words(number) for number in range(NUMERAL_MAX + 1)),
    ]

    seen = set()
    unique_phrases = []
    for phrase in phrases:
        normalized = phrase.strip().lower()
        if normalized and normalized not in seen:
            unique_phrases.append(normalized)
            seen.add(normalized)

    return unique_phrases


def audio_callback(indata, frames, time_info, status) -> None:
    if status:
        print(f"\nAudio warning: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))


def write_partial(text: str) -> None:
    global last_partial_len

    line = f"Partial: {text}" if text else ""
    padding = " " * max(last_partial_len - len(line), 0)
    print(f"\r{line}{padding}", end="", flush=True)
    last_partial_len = len(line)


def write_final(text: str) -> None:
    global last_partial_len

    if not text:
        return

    padding = " " * last_partial_len
    print(f"\r{padding}\r{text}", flush=True)
    last_partial_len = 0
    post_transcript(text)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    SetLogLevel(-1)

    print(f"[voice] Transcript relay: {VOICE_TRANSCRIPT_URL}", flush=True)

    model_path = find_model_path()
    if not model_path.exists():
        raise FileNotFoundError(f"Model folder was not found: {model_path}")

    print(f"[voice] Loading Vosk model: {model_path}", flush=True)
    started_at = time.perf_counter()
    model = Model(str(model_path))
    print(f"[voice] Vosk model loaded in {time.perf_counter() - started_at:.1f}s", flush=True)

    print("[voice] Building recognizer grammar...", flush=True)
    grammar = build_grammar()
    recognizer = KaldiRecognizer(
        model,
        SAMPLE_RATE,
        json.dumps(grammar, ensure_ascii=False),
    )
    recognizer.SetWords(False)

    print(f"[voice] Recognizer ready. Grammar phrases: {len(grammar)}", flush=True)
    print("[voice] Opening microphone stream...", flush=True)

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=CHANNELS,
            callback=audio_callback,
        ):
            print("[voice] Microphone ready. Speak Russian into the microphone. Press Ctrl+C to stop.", flush=True)
            while True:
                data = audio_queue.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    write_final(result.get("text", ""))
                else:
                    partial = json.loads(recognizer.PartialResult())
                    write_partial(partial.get("partial", ""))
    except KeyboardInterrupt:
        print("\nStopping recognition...")
        final = json.loads(recognizer.FinalResult())
        write_final(final.get("text", ""))


if __name__ == "__main__":
    main()
