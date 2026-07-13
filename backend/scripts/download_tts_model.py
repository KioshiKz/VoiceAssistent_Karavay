"""Prefetch the Silero TTS model so the first /api/voice/speak call isn't slow.

Run manually: python backend/scripts/download_tts_model.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import tts_service  # noqa: E402


def main() -> None:
    path = tts_service.ensure_model_file()
    print(f"Silero TTS model ready at {path}")


if __name__ == "__main__":
    main()
