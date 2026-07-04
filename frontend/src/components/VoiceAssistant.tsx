import { useCallback, useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { voiceApi } from "../api/endpoints";

type VoiceCommand = "advance" | "rewind" | "start";

interface SpeechRecognitionResultLike {
  readonly transcript: string;
}

interface SpeechRecognitionAlternativeLike {
  [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike {
  results: {
    readonly length: number;
    [index: number]: SpeechRecognitionAlternativeLike;
  };
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

function emitVoiceCommand(command: VoiceCommand) {
  window.dispatchEvent(new CustomEvent("voice-command", { detail: { command } }));
}

function emitVoiceTranscript(text: string) {
  const event = new CustomEvent("voice-transcript", { detail: { text }, cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

export function VoiceAssistant() {
  const navigate = useNavigate();
  const [supported, setSupported] = useState(true);
  const [armed, setArmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const armedRef = useRef(false);
  const runningRef = useRef(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const clearTimerRef = useRef<number | null>(null);
  const lastRelayIdRef = useRef(Number(window.sessionStorage.getItem("voice-relay-last-id") ?? "0"));
  const lastTextRef = useRef({ text: "", at: 0 });

  const showMessage = useCallback((next: string | null) => {
    setMessage(next);
    if (clearTimerRef.current) window.clearTimeout(clearTimerRef.current);
    if (next) {
      clearTimerRef.current = window.setTimeout(() => setMessage(null), 3500);
    }
  }, []);

  const setArmedState = useCallback((next: boolean) => {
    armedRef.current = next;
    setArmed(next);
  }, []);

  const handleCommand = useCallback((text: string) => {
    if (text.includes("открыть текущую заявку")) {
      navigate("/execution");
      showMessage("Открываю выполнение заявки");
      setArmedState(false);
      return;
    }
    if (text.includes("дальше")) {
      emitVoiceCommand("advance");
      showMessage("Команда: дальше");
      setArmedState(false);
      return;
    }
    if (text.includes("вернуться") || text.includes("вернутся") || text.includes("назад")) {
      emitVoiceCommand("rewind");
      showMessage("Команда: вернуться");
      setArmedState(false);
      return;
    }
    if (text.includes("старт")) {
      emitVoiceCommand("start");
      showMessage("Команда: старт");
      setArmedState(false);
      return;
    }
    if (emitVoiceTranscript(text)) {
      showMessage("Кодовая фраза принята");
      setArmedState(false);
      return;
    }

    showMessage("Не верная команда");
  }, [navigate, setArmedState, showMessage]);

  const handleText = useCallback((rawText: string) => {
    const text = rawText.toLowerCase().trim();
    if (!text) return;

    const now = Date.now();
    if (lastTextRef.current.text === text && now - lastTextRef.current.at < 1500) return;
    lastTextRef.current = { text, at: now };

    if (text.includes("отмена")) {
      showMessage("Слушание команды отменено");
      setArmedState(false);
      return;
    }

    if (!armedRef.current) {
      if (text.includes("помощник")) {
        setArmedState(true);
        showMessage("Слушаю команду");
        const commandText = text.replace("помощник", "").trim();
        if (commandText) handleCommand(commandText);
      }
      return;
    }

    handleCommand(text);
  }, [handleCommand, setArmedState, showMessage]);

  useEffect(() => {
    let cancelled = false;

    const pollVoiceEvents = async () => {
      try {
        const events = await voiceApi.events(lastRelayIdRef.current);
        if (cancelled) return;

        for (const event of events) {
          if (event.id <= lastRelayIdRef.current) continue;
          lastRelayIdRef.current = Math.max(lastRelayIdRef.current, event.id);
          window.sessionStorage.setItem("voice-relay-last-id", String(lastRelayIdRef.current));
          handleText(event.text);
        }
      } catch {
        // The local backend may be restarting while the dev server is open.
      }
    };

    void pollVoiceEvents();
    const interval = window.setInterval(() => {
      void pollVoiceEvents();
    }, 700);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [handleText]);

  useEffect(() => {
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) {
      setSupported(false);
      return;
    }

    const recognition = new Recognition();
    recognition.lang = "ru-RU";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result?.[0]?.transcript ?? "";
      handleText(transcript);
    };
    recognition.onerror = () => showMessage("Голосовой ввод недоступен");
    recognition.onend = () => {
      if (!runningRef.current) return;
      window.setTimeout(() => {
        try {
          recognition.start();
        } catch {
          // Browser can throw if recognition is already starting.
        }
      }, 300);
    };

    recognitionRef.current = recognition;
    runningRef.current = true;
    try {
      recognition.start();
    } catch {
      setSupported(false);
    }

    return () => {
      runningRef.current = false;
      recognition.stop();
      recognitionRef.current = null;
      if (clearTimerRef.current) window.clearTimeout(clearTimerRef.current);
    };
  }, [handleText, showMessage]);

  if (!armed && !message) return null;

  return (
    <div className={`voice-assistant${armed ? " armed" : ""}`} role="status" aria-live="polite">
      <span className="voice-orb">
        <Mic size={18} />
      </span>
      <span>{message ?? (supported ? "Слушаю команду" : "Слушаю Vosk")}</span>
    </div>
  );
}
