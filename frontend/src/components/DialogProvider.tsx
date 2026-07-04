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

/** Replaces native blocking dialogs so the app keeps one visual language. */
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
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <div>
                <h2>
                  {pending.kind === "alert" && "Сообщение"}
                  {pending.kind === "confirm" && "Подтверждение"}
                  {pending.kind === "prompt" && "Введите значение"}
                </h2>
              </div>
            </div>
            <div className="modal-body">
              <p className="dialog-message">{pending.message}</p>
              {pending.kind === "prompt" && (
                <input
                  autoFocus
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") resolve(inputValue);
                    if (event.key === "Escape") resolve(null);
                  }}
                />
              )}
            </div>
            <div className="modal-footer">
              {pending.kind === "alert" && (
                <button className="primary" type="button" onClick={() => resolve(undefined)}>
                  Ок
                </button>
              )}
              {pending.kind === "confirm" && (
                <>
                  <button type="button" onClick={() => resolve(false)}>
                    Отмена
                  </button>
                  <button className="primary" type="button" onClick={() => resolve(true)}>
                    Да
                  </button>
                </>
              )}
              {pending.kind === "prompt" && (
                <>
                  <button type="button" onClick={() => resolve(null)}>
                    Отмена
                  </button>
                  <button className="primary" type="button" onClick={() => resolve(inputValue)}>
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
