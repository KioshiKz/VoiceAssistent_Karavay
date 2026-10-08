import { useCallback, useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { voiceApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { speak } from "../utils/speech";

type VoiceCommand = "advance" | "rewind" | "start" | "stop" | "fullscreen" | "repeat" | "announce";
type VoiceCue = "wake" | "success" | "error";

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

interface SpeechRecognitionErrorEventLike {
  error: string;
  message?: string;
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
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

function emitVoiceCommand(command: VoiceCommand): boolean {
  const event = new CustomEvent("voice-command", { detail: { command }, cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

function emitVoiceTranscript(text: string) {
  const event = new CustomEvent("voice-transcript", { detail: { text }, cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

function playVoiceCue(cue: VoiceCue) {
  const AudioContextCtor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) return;

  const sequences: Record<VoiceCue, Array<[number, number]>> = {
    wake: [
      [740, 0.08],
      [980, 0.1],
    ],
    success: [
      [620, 0.07],
      [840, 0.09],
    ],
    error: [[180, 0.18]],
  };

  try {
    const context = new AudioContextCtor();
    if (context.state === "suspended") void context.resume();
    let offset = 0;
    for (const [frequency, duration] of sequences[cue]) {
      const start = context.currentTime + offset;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = cue === "error" ? "sawtooth" : "sine";
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(0.08, start);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + duration);
      offset += duration + 0.04;
    }
    window.setTimeout(() => void context.close(), Math.ceil((offset + 0.1) * 1000));
  } catch {
    // Browser audio may be blocked until the page receives a user gesture.
  }
}

export function VoiceAssistant() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const voiceEnabled = user?.voice_assistant_enabled !== false;
  const [supported, setSupported] = useState(true);
  const [usingVosk, setUsingVosk] = useState(false);
  const [armed, setArmed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const armedRef = useRef(false);
  const clearTimerRef = useRef<number | null>(null);
  const armedTimerRef = useRef<number | null>(null);
  const lastRelayIdRef = useRef(Number(window.sessionStorage.getItem("voice-relay-last-id") ?? "0"));
  const lastTextRef = useRef({ text: "", at: 0 });
  const assistantSpeakingRef = useRef(false);

  const showMessage = useCallback((next: string | null, persistent = false) => {
    setMessage(next);
    if (clearTimerRef.current) window.clearTimeout(clearTimerRef.current);
    if (next && !persistent) {
      clearTimerRef.current = window.setTimeout(() => setMessage(null), 3500);
    }
  }, []);

  const setArmedState = useCallback((next: boolean) => {
    if (armedTimerRef.current) window.clearTimeout(armedTimerRef.current);
    armedRef.current = next;
    setArmed(next);
    if (next) {
      armedTimerRef.current = window.setTimeout(() => {
        armedRef.current = false;
        setArmed(false);
      }, 8000);
    }
  }, []);

  const handleCommand = useCallback((text: string) => {
    if (text.includes("полный экран")) {
      window.sessionStorage.setItem("execution-fullscreen-requested", "1");
      emitVoiceCommand("fullscreen");
      navigate("/execution");
      showMessage("Открываю полный экран");
      playVoiceCue("success");
      setArmedState(false);
      return;
    }
    if (
      text.includes("открыть текущую заявку") ||
      text.includes("открыть заявку") ||
      text.includes("текущая заявка") ||
      text.includes("заявки")
    ) {
      navigate("/execution");
      // Fires immediately if ExecutionPanel is already mounted (re-announces
      // the current step even though it was already spoken once); on a fresh
      // navigation the panel's own mount-time effect announces it instead.
      emitVoiceCommand("announce");
      showMessage("Открываю выполнение заявки");
      playVoiceCue("success");
      setArmedState(false);
      return;
    }
    if (text.includes("остановить") || text.includes("стоп")) {
      const handled = emitVoiceCommand("stop");
      showMessage(handled ? "Таймер остановлен" : "Сейчас нечего останавливать");
      playVoiceCue(handled ? "success" : "error");
      setArmedState(false);
      return;
    }
    if (text.includes("дальше") || text.includes("некст") || text.includes("продолжить")) {
      const handled = emitVoiceCommand("advance");
      showMessage(handled ? "Команда: дальше" : "Сейчас нельзя перейти дальше");
      playVoiceCue(handled ? "success" : "error");
      setArmedState(false);
      return;
    }
    if (text.includes("вернуться") || text.includes("вернутся") || text.includes("назад")) {
      const handled = emitVoiceCommand("rewind");
      showMessage(handled ? "Команда: вернуться" : "Нельзя вернуться назад");
      playVoiceCue(handled ? "success" : "error");
      setArmedState(false);
      return;
    }
    if (text.includes("старт")) {
      const handled = emitVoiceCommand("start");
      showMessage(handled ? "Команда: старт" : "Сейчас нет таймера для старта");
      playVoiceCue(handled ? "success" : "error");
      setArmedState(false);
      return;
    }
    if (text.includes("повтори")) {
      const handled = emitVoiceCommand("repeat");
      showMessage(handled ? "Повторяю" : "Нечего повторять");
      playVoiceCue(handled ? "success" : "error");
      setArmedState(false);
      return;
    }
    if (emitVoiceTranscript(text)) {
      showMessage("Команда принята");
      playVoiceCue("success");
      setArmedState(false);
      return;
    }

    showMessage("Неверная команда");
    playVoiceCue("error");
    void speak("Команда не распознана. Для новой команды снова скажите: помощник.");
    setArmedState(false);
  }, [navigate, setArmedState, showMessage]);

  const handleText = useCallback((rawText: string) => {
    if (assistantSpeakingRef.current) return;
    const text = rawText.toLowerCase().trim();
    if (!text) return;

    const now = Date.now();
    if (lastTextRef.current.text === text && now - lastTextRef.current.at < 1500) return;
    lastTextRef.current = { text, at: now };

    if (armedRef.current && text.includes("отмена")) {
      showMessage("Слушание команды отменено");
      setArmedState(false);
      return;
    }

    if (!armedRef.current) {
      if (text.includes("помощник")) {
        setArmedState(true);
        showMessage("Слушаю команду");
        playVoiceCue("wake");
        const commandText = text.replace("помощник", "").trim();
        if (commandText) handleCommand(commandText);
      }
      return;
    }

    handleCommand(text);
  }, [handleCommand, setArmedState, showMessage]);

  useEffect(() => {
    const onAssistantSpeaking = (event: Event) => {
      assistantSpeakingRef.current = !!(event as CustomEvent<{ active: boolean }>).detail?.active;
    };
    window.addEventListener("assistant-speaking", onAssistantSpeaking);
    return () => window.removeEventListener("assistant-speaking", onAssistantSpeaking);
  }, []);

  useEffect(() => () => {
    if (clearTimerRef.current) window.clearTimeout(clearTimerRef.current);
    if (armedTimerRef.current) window.clearTimeout(armedTimerRef.current);
  }, []);

  useEffect(() => {
    if (!voiceEnabled) return;
    let cancelled = false;
    let timeout: number | undefined;
    const controller = new AbortController();

    const pollVoiceEvents = async () => {
      try {
        const events = await voiceApi.events(lastRelayIdRef.current, controller.signal);
        if (cancelled) return;

        for (const event of events) {
          if (event.id <= lastRelayIdRef.current) continue;
          lastRelayIdRef.current = Math.max(lastRelayIdRef.current, event.id);
          window.sessionStorage.setItem("voice-relay-last-id", String(lastRelayIdRef.current));
          if (event.source === "vosk") {
            setUsingVosk(true);
            setSupported(true);
          }
          handleText(event.text);
        }
      } catch {
        // The local backend may be restarting while the dev server is open.
      } finally {
        if (!cancelled) timeout = window.setTimeout(() => void pollVoiceEvents(), 700);
      }
    };

    void pollVoiceEvents();

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [handleText, voiceEnabled]);

  useEffect(() => {
    if (!voiceEnabled) return;
    if (!window.isSecureContext) {
      setUsingVosk(true);
      setSupported(true);
      showMessage("Vosk активен · скажите «помощник»", true);
      return;
    }
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) {
      setUsingVosk(true);
      setSupported(true);
      showMessage("Vosk активен · скажите «помощник»", true);
      return;
    }

    let active = true;
    let restartTimer: number | null = null;
    const stopWithError = (error: string, details?: string) => {
      active = false;
      if (restartTimer !== null) window.clearTimeout(restartTimer);
      console.warn("Speech recognition failed:", error, details ?? "");
      if (["network", "service-not-allowed", "language-not-supported"].includes(error)) {
        setUsingVosk(true);
        setSupported(true);
        showMessage("Vosk активен · скажите «помощник»", true);
        return;
      }
      setSupported(false);
      const messages: Record<string, string> = {
        "not-allowed": "Доступ к микрофону запрещён. Разрешите его в настройках сайта и включите помощника заново",
        "service-not-allowed": "Браузер запретил сервис распознавания речи. Можно использовать Vosk",
        "audio-capture": "Не удалось получить звук с микрофона. Проверьте подключение и доступ к нему",
        network: "Не удалось подключиться к сервису распознавания речи. Проверьте сеть или используйте Vosk",
        "language-not-supported": "Сервис распознавания речи не поддерживает русский язык. Можно использовать Vosk",
      };
      const message = messages[error] ?? `Ошибка голосового ввода: ${error}`;
      showMessage(message, true);
      void speak(message);
    };
    const handleStartError = (error: unknown) => {
      const name = error instanceof Error ? error.name : "unknown";
      const code = name === "NotAllowedError" || name === "SecurityError" ? "not-allowed" : name;
      stopWithError(code, error instanceof Error ? error.message : String(error));
    };
    const recognition = new Recognition();
    setSupported(true);
    recognition.lang = "ru-RU";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result?.[0]?.transcript ?? "";
      handleText(transcript);
    };
    recognition.onerror = (event) => {
      // Silence and cancellation are normal recognition lifecycle events.
      if (event.error === "no-speech" || event.error === "aborted") return;
      stopWithError(event.error, event.message);
    };
    recognition.onend = () => {
      if (!active) return;
      if (restartTimer !== null) window.clearTimeout(restartTimer);
      restartTimer = window.setTimeout(() => {
        restartTimer = null;
        if (!active) return;
        try {
          recognition.start();
        } catch (error) {
          // Recognition may already be starting; other failures need diagnostics.
          if (!(error instanceof Error && error.name === "InvalidStateError")) handleStartError(error);
        }
      }, 300);
    };

    try {
      recognition.start();
    } catch (error) {
      handleStartError(error);
    }

    return () => {
      active = false;
      if (restartTimer !== null) window.clearTimeout(restartTimer);
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.stop();
      if (clearTimerRef.current) window.clearTimeout(clearTimerRef.current);
      if (armedTimerRef.current) window.clearTimeout(armedTimerRef.current);
    };
  }, [handleText, showMessage, voiceEnabled]);

  if (!voiceEnabled) return null;
  return (
    <div className={`voice-assistant${armed ? " armed" : ""}${!supported ? " voice-error" : ""}`} role="status" aria-live="polite">
      <span className="voice-orb">
        <Mic size={18} />
      </span>
      <span>{message ?? (armed ? "Слушаю команду" : usingVosk ? "Vosk активен · скажите «помощник»" : supported ? "Голос готов · скажите «помощник»" : "Голос недоступен")}</span>
    </div>
  );
}
