import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ordersApi } from "../api/endpoints";
import type { CurrentOrderOut, OrderLineOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";
import { ExecutionPanel } from "../components/ExecutionPanel";
import { VoiceAssistant } from "../components/VoiceAssistant";
import { speak } from "../utils/speech";

function statusLabel(status: OrderLineOut["status"]) {
  if (status === "pending") return "ожидает";
  if (status === "in_progress") return "в работе";
  if (status === "completed") return "готово";
  return "отменена";
}

const NUMBER_WORD_VALUES: Record<string, number> = {
  ноль: 0,
  один: 1,
  одна: 1,
  два: 2,
  две: 2,
  три: 3,
  четыре: 4,
  пять: 5,
  шесть: 6,
  семь: 7,
  восемь: 8,
  девять: 9,
  десять: 10,
  одиннадцать: 11,
  двенадцать: 12,
  тринадцать: 13,
  четырнадцать: 14,
  пятнадцать: 15,
  шестнадцать: 16,
  семнадцать: 17,
  восемнадцать: 18,
  девятнадцать: 19,
  двадцать: 20,
  тридцать: 30,
  сорок: 40,
  пятьдесят: 50,
  шестьдесят: 60,
  семьдесят: 70,
  восемьдесят: 80,
  девяносто: 90,
  сто: 100,
  двести: 200,
  триста: 300,
  четыреста: 400,
  пятьсот: 500,
  шестьсот: 600,
  семьсот: 700,
  восемьсот: 800,
  девятьсот: 900,
};

const PRODUCT_QUERY_STOP_WORDS = new Set(["заявка", "заявку", "количество", "штук", "штуки", "штука", "шт"]);
const TIME_QUERY_STOP_WORDS = new Set([
  "заявка",
  "заявку",
  "время",
  "заявки",
  "в",
  "на",
  "к",
  "час",
  "часа",
  "часов",
  "минут",
  "минуты",
  "минута",
]);

function normalizeVoiceText(value: string) {
  return value
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^\p{L}\p{N}:.\s-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeWordText(value: string) {
  return normalizeVoiceText(value).replace(/[:.-]/g, " ").replace(/\s+/g, " ").trim();
}

function tokenizeWords(value: string) {
  const normalized = normalizeWordText(value);
  return normalized ? normalized.split(" ") : [];
}

function parseRussianNumberWords(words: string[]) {
  if (!words.length) return null;

  let value = 0;
  for (const word of words) {
    const next = NUMBER_WORD_VALUES[word];
    if (next === undefined) return null;
    value += next;
  }
  return value;
}

function formatTimeValue(hour: number, minute: number) {
  if (!Number.isInteger(hour) || !Number.isInteger(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null;
  }
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function parseTimeQuery(query: string) {
  const normalized = normalizeVoiceText(query);
  const direct = normalized.match(/(?:^|\s)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?:\s|$)/);
  if (direct) return formatTimeValue(Number(direct[1]), Number(direct[2]));

  const tokens = tokenizeWords(query).filter((token) => !TIME_QUERY_STOP_WORDS.has(token));
  if (!tokens.length) return null;

  if (tokens.every((token) => /^\d+$/.test(token))) {
    if (tokens.length === 1) {
      const raw = tokens[0];
      if (raw.length === 3 || raw.length === 4) {
        return formatTimeValue(Number(raw.slice(0, -2)), Number(raw.slice(-2)));
      }
      return formatTimeValue(Number(raw), 0);
    }
    if (tokens.length === 2) return formatTimeValue(Number(tokens[0]), Number(tokens[1]));
  }

  for (let split = 1; split < tokens.length; split += 1) {
    const hour = parseRussianNumberWords(tokens.slice(0, split));
    const minute = parseRussianNumberWords(tokens.slice(split));
    const parsed = hour === null || minute === null ? null : formatTimeValue(hour, minute);
    if (parsed) return parsed;
  }

  const hour = parseRussianNumberWords(tokens);
  return hour === null ? null : formatTimeValue(hour, 0);
}

function parseQuantityQuery(query: string) {
  let tokens = tokenizeWords(query);
  while (tokens.length && PRODUCT_QUERY_STOP_WORDS.has(tokens[tokens.length - 1])) {
    tokens = tokens.slice(0, -1);
  }
  if (!tokens.length) return null;

  const buildResult = (quantity: number, quantityTokenCount: number) => {
    if (quantity <= 0) return null;
    const productTokens = tokens
      .slice(0, tokens.length - quantityTokenCount)
      .filter((token) => !PRODUCT_QUERY_STOP_WORDS.has(token));
    if (!productTokens.length) return null;
    return { productQuery: productTokens.join(" "), quantity };
  };

  const lastToken = tokens[tokens.length - 1];
  if (/^\d+$/.test(lastToken)) return buildResult(Number(lastToken), 1);

  for (let length = Math.min(4, tokens.length); length >= 1; length -= 1) {
    const quantity = parseRussianNumberWords(tokens.slice(tokens.length - length));
    if (quantity !== null) {
      const result = buildResult(quantity, length);
      if (result) return result;
    }
  }

  return null;
}

function productMatchesQuery(line: OrderLineOut, productQuery: string) {
  const productText = normalizeWordText(line.product_name_raw);
  return productQuery.split(" ").every((token) => productText.includes(token));
}

function extractDirectTime(query: string): { time: string; remainder: string } | null {
  const normalized = normalizeVoiceText(query);

  // "14:30" / "14.30" — punctuation form (rare from speech, common if typed).
  const punctuated = normalized.match(/(?:^|\s)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?:\s|$)/);
  // "14 30" — two bare digit tokens, which is what speech recognition actually
  // produces for spoken times (no colon gets inserted).
  const bareDigits = normalized.match(/(?:^|\s)([01]?\d|2[0-3])\s+([0-5]\d)(?:\s|$)/);
  const match = punctuated ?? bareDigits;
  if (!match || match.index === undefined) return null;

  const time = formatTimeValue(Number(match[1]), Number(match[2]));
  if (!time) return null;

  const before = normalized.slice(0, match.index);
  const after = normalized.slice(match.index + match[0].length);
  const remainderTokens = tokenizeWords(`${before} ${after}`).filter(
    (token) => !TIME_QUERY_STOP_WORDS.has(token) && !PRODUCT_QUERY_STOP_WORDS.has(token),
  );
  return { time, remainder: remainderTokens.join(" ") };
}

function announceLine(time: string, line: OrderLineOut) {
  void speak(`Заявка на ${time.replace(":", " ")}: ${line.product_name_raw}, ${line.quantity} штук.`);
}

export function ExecutionQueue() {
  const [order, setOrder] = useState<CurrentOrderOut | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(() => window.sessionStorage.getItem("execution-fullscreen-requested") === "1");
  const [loading, setLoading] = useState(false);
  const [empty, setEmpty] = useState(false);

  const setExecutionFullscreen = useCallback((next: boolean) => {
    setFullscreen(next);
    if (next) window.sessionStorage.setItem("execution-fullscreen-requested", "1");
    else window.sessionStorage.removeItem("execution-fullscreen-requested");

    if (next && !document.fullscreenElement) {
      void document.documentElement.requestFullscreen?.().catch(() => undefined);
    }
    if (!next && document.fullscreenElement) {
      void document.exitFullscreen?.().catch(() => undefined);
    }
  }, []);

  function reload() {
    setLoading(true);
    ordersApi
      .current()
      .then((next) => {
        setOrder(next);
        setEmpty(false);
      })
      .catch(() => {
        setOrder(null);
        setEmpty(true);
      })
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  useEffect(() => {
    function onVoiceCommand(event: Event) {
      const command = (event as CustomEvent<{ command: string }>).detail?.command;
      if (command === "fullscreen") setExecutionFullscreen(true);
    }

    window.addEventListener("voice-command", onVoiceCommand);
    return () => window.removeEventListener("voice-command", onVoiceCommand);
  }, [setExecutionFullscreen]);

  const groups = useMemo(() => {
    const map = new Map<string, OrderLineOut[]>();
    for (const line of order?.lines ?? []) {
      const key = line.workshop_folder_name ?? "Без цеха";
      map.set(key, [...(map.get(key) ?? []), line]);
    }
    return [...map.entries()];
  }, [order]);

  const selectableLines = useMemo(
    () => (order?.lines ?? []).filter((line) => line.match_status === "matched" && line.status !== "cancelled"),
    [order],
  );

  useEffect(() => {
    if (!selectableLines.length) {
      setSelectedLineId(null);
      return;
    }
    if (selectedLineId && selectableLines.some((line) => line.id === selectedLineId)) return;
    setSelectedLineId(selectableLines[0].id);
  }, [selectableLines, selectedLineId]);

  const selectRelativeLine = useCallback(
    (offset: number) => {
      if (!selectableLines.length) return false;
      const currentIndex = selectableLines.findIndex((line) => line.id === selectedLineId);
      const nextIndex =
        currentIndex === -1
          ? offset > 0
            ? 0
            : selectableLines.length - 1
          : (currentIndex + offset + selectableLines.length) % selectableLines.length;
      setSelectedLineId(selectableLines[nextIndex].id);
      return true;
    },
    [selectableLines, selectedLineId],
  );

  const findFirstMatchingLine = useCallback(
    (predicate: (line: OrderLineOut) => boolean) => {
      if (!selectableLines.length) return null;
      const currentIndex = selectableLines.findIndex((line) => line.id === selectedLineId);
      const searchOrder =
        currentIndex === -1
          ? selectableLines
          : [...selectableLines.slice(currentIndex + 1), ...selectableLines.slice(0, currentIndex + 1)];
      return searchOrder.find(predicate) ?? null;
    },
    [selectableLines, selectedLineId],
  );

  const selectFirstMatchingLine = useCallback(
    (predicate: (line: OrderLineOut) => boolean) => {
      const match = findFirstMatchingLine(predicate);
      if (!match) return false;
      setSelectedLineId(match.id);
      return true;
    },
    [findFirstMatchingLine],
  );

  const handleOrderVoiceTranscript = useCallback(
    (rawText: string) => {
      const text = normalizeVoiceText(rawText);
      if (!text) return false;

      if (text.includes("следующая заявка") || text.includes("следущая заявка")) {
        return selectRelativeLine(1);
      }
      if (text.includes("предыдущая заявка") || text.includes("прошлая заявка")) {
        return selectRelativeLine(-1);
      }

      const markerIndex = text.indexOf("заявка");
      if (markerIndex === -1) return false;

      const query = text.slice(markerIndex + "заявка".length).trim();
      if (!query) return false;

      // Digit-form time ("14:30", "14.30") lets us isolate a remaining product
      // phrase, so "продукт + время" and bare "время" can be told apart.
      const direct = extractDirectTime(query);
      if (direct) {
        if (direct.remainder) {
          return selectFirstMatchingLine(
            (line) => line.due_time.slice(0, 5) === direct.time && productMatchesQuery(line, direct.remainder),
          );
        }
        const match = findFirstMatchingLine((line) => line.due_time.slice(0, 5) === direct.time);
        if (!match) return false;
        setSelectedLineId(match.id);
        announceLine(direct.time, match);
        return true;
      }

      // Word-form time ("четырнадцать тридцать") only supports the bare-time case.
      const time = parseTimeQuery(query);
      if (time) {
        const match = findFirstMatchingLine((line) => line.due_time.slice(0, 5) === time);
        if (match) {
          setSelectedLineId(match.id);
          announceLine(time, match);
          return true;
        }
      }

      const quantityQuery = parseQuantityQuery(query);
      if (!quantityQuery) return false;

      return selectFirstMatchingLine(
        (line) => line.quantity === quantityQuery.quantity && productMatchesQuery(line, quantityQuery.productQuery),
      );
    },
    [findFirstMatchingLine, selectFirstMatchingLine, selectRelativeLine],
  );

  useEffect(() => {
    function onVoiceTranscript(event: Event) {
      if (event.defaultPrevented) return;
      const text = (event as CustomEvent<{ text: string }>).detail?.text ?? "";
      if (handleOrderVoiceTranscript(text)) event.preventDefault();
    }

    window.addEventListener("voice-transcript", onVoiceTranscript);
    return () => window.removeEventListener("voice-transcript", onVoiceTranscript);
  }, [handleOrderVoiceTranscript]);

  if (fullscreen && order && selectedLineId) {
    return (
      <div className="execution-fullscreen-page">
        <ExecutionPanel orderLineId={selectedLineId} fullscreen onFullscreenChange={setExecutionFullscreen} />
        <VoiceAssistant />
      </div>
    );
  }

  return (
    <ConsoleShell
      title="Выполнение заявки"
      subtitle="Очередь видна только в пределах цехов и количества позиций, разрешённых ролью."
      actions={
        <button type="button" onClick={reload} disabled={loading}>
          <RefreshCw size={17} />
          Обновить
        </button>
      }
    >
      {empty || !order ? (
        <div className="empty-state">Заявки пока нет - ожидайте</div>
      ) : (
        <div className="execution-workspace">
          <aside className="execution-queue-panel">
            <div className="pane-heading">
              <div>
                <p className="eyebrow">Очередь</p>
                <h2>{order.execution_date}</h2>
              </div>
            </div>

            {groups.map(([groupName, lines]) => (
              <section className="execution-group" key={groupName}>
                <h3>{groupName}</h3>
                {lines.map((line) => {
                  const disabled = line.match_status !== "matched" || line.status === "cancelled";
                  return (
                    <button
                      key={line.id}
                      type="button"
                      className={`execution-line-button${selectedLineId === line.id ? " active" : ""}`}
                      onClick={() => setSelectedLineId(line.id)}
                      disabled={disabled}
                    >
                      <span>
                        <strong>{line.product_name_raw}</strong>
                        <small>
                          {line.due_time.slice(0, 5)} · {line.quantity} шт · {statusLabel(line.status)}
                        </small>
                      </span>
                    </button>
                  );
                })}
              </section>
            ))}
          </aside>

          <section className="execution-center">
            <ExecutionPanel orderLineId={selectedLineId} fullscreen={fullscreen} onFullscreenChange={setExecutionFullscreen} />
          </section>
        </div>
      )}
    </ConsoleShell>
  );
}
