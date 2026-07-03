import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

interface DialogContextValue {
  alertMessage: (message: string) => void;
  confirmAction: (message: string) => Promise<boolean>;
  promptText: (message: string, defaultValue?: string) => Promise<string | null>;
}

const DialogContext = createContext<DialogContextValue | null>(null);

type PendingDialog =
  | { kind: "alert"; message: string }
  | { kind: "confirm"; message: string }
  | { kind: "prompt"; message: string; defaultValue: string };

/** Replaces window.alert/confirm/prompt: those are blocking native dialogs that
 * freeze the whole tab (and hang headless/automated testing) until dismissed. */
export function DialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingDialog | null>(null);
  const [inputValue, setInputValue] = useState("");
  const resolverRef = useRef<((value: never) => void) | null>(null);

  const alertMessage = useCallback((message: string) => {
    setPending({ kind: "alert", message });
  }, []);

  const confirmAction = useCallback((message: string) => {
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve as (value: never) => void;
      setPending({ kind: "confirm", message });
    });
  }, []);

  const promptText = useCallback((message: string, defaultValue = "") => {
    setInputValue(defaultValue);
    return new Promise<string | null>((resolve) => {
      resolverRef.current = resolve as (value: never) => void;
      setPending({ kind: "prompt", message, defaultValue });
    });
  }, []);

  function close() {
    setPending(null);
  }

  function resolve(value: unknown) {
    resolverRef.current?.(value as never);
    resolverRef.current = null;
    close();
  }

  return (
    <DialogContext.Provider value={{ alertMessage, confirmAction, promptText }}>
      {children}
      {pending && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div style={{ background: "#fff", borderRadius: 8, padding: 20, minWidth: 320 }}>
            <p style={{ marginTop: 0 }}>{pending.message}</p>
            {pending.kind === "prompt" && (
              <input
                autoFocus
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                style={{ width: "100%", marginBottom: 12 }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") resolve(inputValue);
                  if (e.key === "Escape") resolve(null);
                }}
              />
            )}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              {pending.kind === "alert" && (
                <button className="primary" onClick={() => resolve(undefined)}>
                  Ок
                </button>
              )}
              {pending.kind === "confirm" && (
                <>
                  <button onClick={() => resolve(false)}>Отмена</button>
                  <button className="primary" onClick={() => resolve(true)}>
                    Да
                  </button>
                </>
              )}
              {pending.kind === "prompt" && (
                <>
                  <button onClick={() => resolve(null)}>Отмена</button>
                  <button className="primary" onClick={() => resolve(inputValue)}>
                    Ок
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error("useDialog must be used within DialogProvider");
  return ctx;
}
