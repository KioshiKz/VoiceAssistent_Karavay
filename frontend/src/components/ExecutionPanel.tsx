import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  CheckCircle2,
  Clock3,
  Maximize2,
  Minimize2,
  Play,
  RotateCcw,
  Wheat,
} from "lucide-react";
import { executionApi } from "../api/endpoints";
import type { ExecutionPlanOut, ExecutionPlanStepOut } from "../api/types";
import { speak } from "../utils/speech";

const ACTIVE_TIMER_KEY = "karavay.activeExecutionTimer";
const COMPLETED_TIMERS_KEY = "karavay.completedExecutionTimers";
const CONFIRMED_PHRASES_KEY = "karavay.confirmedExecutionPhrases";

interface ActiveTimer {
  key: string;
  label: string;
  endsAt: number;
}

interface ExecutionPanelProps {
  orderLineId: string | null;
  fullscreen?: boolean;
  onFullscreenChange?: (next: boolean) => void;
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes ? `${minutes} мин ${rest} сек` : `${rest} сек`;
}

function params(step: ExecutionPlanStepOut | undefined): Record<string, unknown> {
  return step?.event_params_snapshot ?? {};
}

function timerDuration(step: ExecutionPlanStepOut | undefined) {
  return Number(params(step).duration_seconds ?? 0);
}

function timerStartPhrase(step: ExecutionPlanStepOut | undefined) {
  return String(params(step).start_phrase ?? "старт").toLowerCase().trim();
}

function confirmationPhrase(step: ExecutionPlanStepOut | undefined) {
  return String(params(step).phrase ?? "").toLowerCase().trim();
}

function stepTitle(step: ExecutionPlanStepOut) {
  if (step.step_type === "ingredient") return step.ingredient_name_snapshot ?? "Ингредиент";
  if (step.step_type === "ingredient_event") return `Постепенно добавить: ${step.ingredient_name_snapshot ?? "ингредиент"}`;
  return step.event_name_snapshot ?? "Событие";
}

function stepDetails(step: ExecutionPlanStepOut) {
  if (step.step_type === "ingredient") return step.quantity_display ?? "";
  if (step.event_type_snapshot === "timer") return `таймер ${formatDuration(timerDuration(step))}`;
  if (step.event_type_snapshot === "phrase_confirmation") {
    return `кодовая фраза: ${params(step).phrase ?? ""}`;
  }
  if (step.event_type_snapshot === "weight_check") {
    return "проверка веса пока не подключена";
  }
  return step.quantity_display ?? "";
}

function stepKey(plan: ExecutionPlanOut, step: ExecutionPlanStepOut) {
  return `${plan.id}:${step.order_index}`;
}

type TimerCue = "start" | "tick" | "done";

function playTimerCue(cue: TimerCue) {
  const AudioContextCtor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) return;

  const sequences: Record<TimerCue, Array<[number, number, number]>> = {
    start: [
      [440, 0.07, 0.08],
      [660, 0.09, 0.08],
    ],
    tick: [[520, 0.035, 0.025]],
    done: [
      [740, 0.1, 0.1],
      [940, 0.1, 0.1],
      [1180, 0.16, 0.1],
    ],
  };

  try {
    const context = new AudioContextCtor();
    if (context.state === "suspended") void context.resume();
    let offset = 0;
    for (const [frequency, duration, volume] of sequences[cue]) {
      const start = context.currentTime + offset;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(volume, start);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + duration);
      offset += duration + 0.05;
    }
    window.setTimeout(() => void context.close(), Math.ceil((offset + 0.1) * 1000));
  } catch {
    // Browser audio may be blocked until the page receives a user gesture.
  }
}

function stepSpeech(step: ExecutionPlanStepOut, stepNumber: number, totalSteps: number) {
  const base = `Шаг ${stepNumber} из ${totalSteps}.`;
  if (step.step_type === "ingredient") {
    return `${base} Добавьте ${step.quantity_display ?? ""}: ${step.ingredient_name_snapshot ?? "ингредиент"}.`;
  }
  if (step.step_type === "ingredient_event") {
    return `${base} Постепенно добавьте ${step.quantity_display ?? ""}: ${
      step.ingredient_name_snapshot ?? "ингредиент"
    }. ${stepDetails(step)}.`;
  }
  if (step.event_type_snapshot === "timer") {
    return `${base} ${step.event_name_snapshot ?? "Событие"}. Для запуска таймера скажите ${timerStartPhrase(step)}.`;
  }
  if (step.event_type_snapshot === "phrase_confirmation") {
    return `${base} ${step.event_name_snapshot ?? "Событие"}. Скажите кодовую фразу ${confirmationPhrase(step)}.`;
  }
  return `${base} ${stepTitle(step)}.`;
}

export function ExecutionPanel({ orderLineId, fullscreen = false, onFullscreenChange }: ExecutionPanelProps) {
  const [plan, setPlan] = useState<ExecutionPlanOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [activeTimer, setActiveTimerState] = useState<ActiveTimer | null>(() => readJson(ACTIVE_TIMER_KEY, null));
  const [completedTimers, setCompletedTimers] = useState<string[]>(() => readJson(COMPLETED_TIMERS_KEY, []));
  const [confirmedPhrases, setConfirmedPhrases] = useState<string[]>(() => readJson(CONFIRMED_PHRASES_KEY, []));
  const announcedStepKeyRef = useRef<string | null>(null);
  const lastTickRef = useRef<number | null>(null);
  const lastSpokenTextRef = useRef<string>("");

  useEffect(() => {
    announcedStepKeyRef.current = null;
    if (!orderLineId) {
      setPlan(null);
      return;
    }
    setLoading(true);
    setError(null);
    executionApi
      .getOrCreate(orderLineId)
      .then(setPlan)
      .catch(() => setError("Не удалось открыть выполнение заявки."))
      .finally(() => setLoading(false));
  }, [orderLineId]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const setActiveTimer = useCallback((next: ActiveTimer | null) => {
    setActiveTimerState(next);
    if (next) localStorage.setItem(ACTIVE_TIMER_KEY, JSON.stringify(next));
    else localStorage.removeItem(ACTIVE_TIMER_KEY);
  }, []);

  const rememberCompletedTimer = useCallback((key: string) => {
    setCompletedTimers((prev) => {
      const next = prev.includes(key) ? prev : [...prev, key];
      localStorage.setItem(COMPLETED_TIMERS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const rememberConfirmedPhrase = useCallback((key: string) => {
    setConfirmedPhrases((prev) => {
      const next = prev.includes(key) ? prev : [...prev, key];
      localStorage.setItem(CONFIRMED_PHRASES_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  useEffect(() => {
    if (!activeTimer || activeTimer.endsAt > now) return;
    playTimerCue("done");
    rememberCompletedTimer(activeTimer.key);
    setActiveTimer(null);
  }, [activeTimer, now, rememberCompletedTimer, setActiveTimer]);

  const currentStep = plan?.steps[plan.current_step_index];
  const currentStepKey = plan && currentStep ? stepKey(plan, currentStep) : null;
  const totalSteps = plan?.total_steps ?? plan?.steps.length ?? 0;
  const currentStepNumber = plan ? Math.min(plan.current_step_index + 1, totalSteps) : 0;
  const isTimerStep = currentStep?.event_type_snapshot === "timer";
  const isPhraseStep = currentStep?.event_type_snapshot === "phrase_confirmation";
  const timerDone = !!currentStepKey && completedTimers.includes(currentStepKey);
  const phraseConfirmed = !!currentStepKey && confirmedPhrases.includes(currentStepKey);
  const timerBlocked = !!currentStep && isTimerStep && !timerDone;
  const phraseBlocked = !!currentStep && isPhraseStep && !phraseConfirmed;
  const activeRemaining = activeTimer ? Math.max(0, Math.ceil((activeTimer.endsAt - now) / 1000)) : 0;
  const hiddenFutureSteps = plan ? Math.max(0, plan.total_steps - plan.steps.length) : 0;

  const progressText = useMemo(() => {
    if (!plan) return "";
    if (plan.status === "completed") return "Все шаги выполнены";
    return `Шаг ${Math.min(plan.current_step_index + 1, plan.total_steps)} из ${plan.total_steps}`;
  }, [plan]);

  useEffect(() => {
    if (!plan || !currentStep || !currentStepKey || plan.status === "completed") return;
    if (announcedStepKeyRef.current === currentStepKey) return;
    announcedStepKeyRef.current = currentStepKey;
    const text = stepSpeech(currentStep, currentStepNumber, totalSteps);
    lastSpokenTextRef.current = text;
    void speak(text);
  }, [currentStep, currentStepKey, currentStepNumber, plan, totalSteps]);

  useEffect(() => {
    if (!activeTimer || activeRemaining <= 0) {
      lastTickRef.current = null;
      return;
    }
    if (lastTickRef.current === activeRemaining) return;
    lastTickRef.current = activeRemaining;
    playTimerCue("tick");
  }, [activeRemaining, activeTimer]);

  const startTimer = useCallback(() => {
    if (!plan || !currentStep || !currentStepKey || !isTimerStep) return false;
    if (timerDone || activeTimer?.key === currentStepKey) {
      setError(null);
      return true;
    }
    const duration = timerDuration(currentStep);
    if (duration <= 0) {
      rememberCompletedTimer(currentStepKey);
      return true;
    }
    playTimerCue("start");
    setActiveTimer({
      key: currentStepKey,
      label: stepTitle(currentStep),
      endsAt: Date.now() + duration * 1000,
    });
    setError(null);
    return true;
  }, [activeTimer?.key, currentStep, currentStepKey, isTimerStep, plan, rememberCompletedTimer, setActiveTimer, timerDone]);

  const confirmPhrase = useCallback(() => {
    if (!currentStepKey) return;
    rememberConfirmedPhrase(currentStepKey);
    setError(null);
  }, [currentStepKey, rememberConfirmedPhrase]);

  const stopTimer = useCallback(() => {
    if (!activeTimer) return false;
    setActiveTimer(null);
    setError(null);
    return true;
  }, [activeTimer, setActiveTimer]);

  const canAdvance = !!plan && !advancing && plan.status !== "completed" && !timerBlocked && !phraseBlocked;
  const canRewind = !!plan && !advancing && plan.current_step_index > 0;

  const advance = useCallback(async () => {
    if (!plan || advancing || plan.status === "completed") return;
    if (timerBlocked) {
      setError(activeTimer?.key === currentStepKey ? "Дождитесь окончания таймера." : "Скажите или нажмите «старт».");
      return;
    }
    if (phraseBlocked) {
      setError("Скажите кодовую фразу, указанную на экране.");
      return;
    }
    setAdvancing(true);
    try {
      const updated = await executionApi.advance(plan.id);
      setPlan(updated);
      setError(null);
    } catch {
      setError("Не удалось перейти к следующему шагу.");
    } finally {
      setAdvancing(false);
    }
  }, [activeTimer?.key, advancing, currentStepKey, phraseBlocked, plan, timerBlocked]);

  const rewind = useCallback(async () => {
    if (!plan || advancing || plan.current_step_index <= 0) return;
    setAdvancing(true);
    try {
      const updated = await executionApi.rewind(plan.id);
      setPlan(updated);
      setError(null);
    } catch {
      setError("Не удалось вернуться назад.");
    } finally {
      setAdvancing(false);
    }
  }, [advancing, plan]);

  useEffect(() => {
    function onVoiceCommand(event: Event) {
      const custom = event as CustomEvent<{ command: string }>;
      const command = custom.detail?.command;
      if (command === "advance" && canAdvance) {
        void advance();
        custom.preventDefault();
      }
      if (command === "rewind" && canRewind) {
        void rewind();
        custom.preventDefault();
      }
      if (command === "start" && startTimer()) {
        custom.preventDefault();
      }
      if (command === "stop" && stopTimer()) {
        custom.preventDefault();
      }
      if (command === "fullscreen" && onFullscreenChange) {
        onFullscreenChange(true);
        custom.preventDefault();
      }
      if (command === "repeat" && lastSpokenTextRef.current) {
        void speak(lastSpokenTextRef.current);
        custom.preventDefault();
      }
      if (command === "announce" && plan) {
        const text =
          plan.status === "completed" || !currentStep || !currentStepKey
            ? "Все шаги выполнены."
            : stepSpeech(currentStep, currentStepNumber, totalSteps);
        lastSpokenTextRef.current = text;
        announcedStepKeyRef.current = currentStepKey;
        void speak(text);
        custom.preventDefault();
      }
    }

    function onVoiceTranscript(event: Event) {
      const text = ((event as CustomEvent<{ text: string }>).detail?.text ?? "").toLowerCase();
      if (!currentStep || !currentStepKey) return;
      if (isTimerStep && text.includes(timerStartPhrase(currentStep))) {
        if (startTimer()) event.preventDefault();
        return;
      }
      if (isPhraseStep && confirmationPhrase(currentStep) && text.includes(confirmationPhrase(currentStep))) {
        confirmPhrase();
        event.preventDefault();
      }
    }

    window.addEventListener("voice-command", onVoiceCommand);
    window.addEventListener("voice-transcript", onVoiceTranscript);
    return () => {
      window.removeEventListener("voice-command", onVoiceCommand);
      window.removeEventListener("voice-transcript", onVoiceTranscript);
    };
  }, [
    advance,
    canAdvance,
    canRewind,
    confirmPhrase,
    currentStep,
    currentStepKey,
    currentStepNumber,
    isPhraseStep,
    isTimerStep,
    onFullscreenChange,
    plan,
    rewind,
    startTimer,
    stopTimer,
    totalSteps,
  ]);

  if (!orderLineId) {
    return <div className="empty-state">Заявка пока не выбрана.</div>;
  }

  if (loading) {
    return <div className="empty-state">Загрузка выполнения...</div>;
  }

  if (!plan) {
    return <div className="empty-state">{error ?? "Выполнение заявки пока недоступно."}</div>;
  }

  return (
    <div className={`execution-panel${fullscreen ? " fullscreen" : ""}`}>
      {activeTimer &&
        activeRemaining > 0 &&
        (fullscreen ? (
          <section className="timer-fullscreen">
            <Clock3 size={58} />
            <strong>{formatDuration(activeRemaining)}</strong>
            <span>{activeTimer.label}</span>
          </section>
        ) : (
          <div className="timer-widget">
            <Clock3 size={17} />
            <strong>{formatDuration(activeRemaining)}</strong>
            <span>{activeTimer.label}</span>
          </div>
        ))}

      <div className="execution-toolbar">
        <div>
          <p className="eyebrow">Выполнение заявки</p>
          <h2>{progressText}</h2>
        </div>
        <div className="action-row">
          {onFullscreenChange && (
            <button type="button" onClick={() => onFullscreenChange(!fullscreen)}>
              {fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              {fullscreen ? "Выйти" : "Полный экран"}
            </button>
          )}
          <button
            type="button"
            onClick={rewind}
            disabled={advancing || plan.status === "completed" || plan.current_step_index <= 0}
          >
            <ArrowLeft size={16} />
            Вернуться
          </button>
          {plan.status !== "completed" && (
            <button className="primary" type="button" onClick={advance} disabled={advancing || timerBlocked || phraseBlocked}>
              <ArrowRight size={16} />
              Дальше
            </button>
          )}
        </div>
      </div>

      <div className="execution-progress">
        {Array.from({ length: totalSteps }).map((_, idx) => (
          <span
            key={`progress-${idx}`}
            className={`dot${idx < plan.current_step_index ? " done" : ""}${idx === plan.current_step_index ? " current" : ""}`}
          />
        ))}
      </div>

      {plan.status === "completed" ? (
        <section className="execution-step-card">
          <CheckCircle2 size={42} />
          <div className="step-kind">Готово</div>
          <div className="step-name">Все шаги выполнены</div>
        </section>
      ) : currentStep ? (
        <section className="execution-step-card">
          <div className="step-kind">
            {currentStep.step_type === "ingredient" ? "Ингредиент" : currentStep.step_type === "ingredient_event" ? "Связанное действие" : "Событие"}
          </div>
          <div className="step-icon">
            {currentStep.step_type === "ingredient" ? <Wheat size={22} /> : <BellRing size={22} />}
          </div>
          <div className="step-name">{stepTitle(currentStep)}</div>
          <div className="step-quantity">{currentStep.step_type === "ingredient_event" ? currentStep.quantity_display : stepDetails(currentStep)}</div>
          {currentStep.step_type === "ingredient_event" && <div className="step-secondary">{stepDetails(currentStep)}</div>}

          {isTimerStep && (
            <div className="execution-code-panel">
              <span>Кодовая фраза</span>
              <strong>{timerStartPhrase(currentStep)}</strong>
              <button type="button" onClick={startTimer} disabled={timerDone || activeTimer?.key === currentStepKey}>
                <Play size={16} />
                Старт
              </button>
            </div>
          )}

          {isPhraseStep && (
            <div className="execution-code-panel">
              <span>Кодовая фраза</span>
              <strong>{confirmationPhrase(currentStep)}</strong>
              <button type="button" onClick={confirmPhrase} disabled={phraseConfirmed}>
                <CheckCircle2 size={16} />
                Подтвердить
              </button>
            </div>
          )}
        </section>
      ) : (
        <section className="execution-step-card">
          <RotateCcw size={34} />
          <div className="step-name">Шаг не найден</div>
        </section>
      )}

      {error && <p className="error-text">{error}</p>}

      <div className="execution-step-list">
        {plan.steps.map((step, idx) => (
          <div key={`${step.order_index}-list`} className={`execution-step-line${idx === plan.current_step_index ? " active" : ""}`}>
            <span>{idx + 1}.</span>
            <strong>{stepTitle(step)}</strong>
            <small>{step.step_type === "ingredient_event" ? `${step.quantity_display ?? ""} · ${stepDetails(step)}` : stepDetails(step)}</small>
          </div>
        ))}
        {hiddenFutureSteps > 0 && (
          <div className="execution-step-line locked">
            <span>...</span>
            <strong>Следующий шаг скрыт</strong>
            <small>Откроется после выполнения текущего шага</small>
          </div>
        )}
      </div>
    </div>
  );
}
