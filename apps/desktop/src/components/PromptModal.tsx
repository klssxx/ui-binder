/** Generic text prompt modal (window.prompt is unreliable in the Tauri webview). */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

export function PromptModal({ title, placeholder, initial = "", validate,
  onSubmit, onCancel, children }: {
  title: string; placeholder?: string; initial?: string;
  validate?: (value: string) => string | null;
  onSubmit: (value: string) => void; onCancel: () => void;
  children?: ReactNode;
}) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setError(validate ? validate(value) : null), [value, validate]);

  const submit = () => {
    const problem = validate ? validate(value) : null;
    if (problem) { setError(problem); return; }
    onSubmit(value);
  };

  return (
    <div className="overlay" onPointerDown={onCancel}>
      <div className="modal modal-small" onPointerDown={(e) => e.stopPropagation()}>
        <div className="modal-title">{title}</div>
        <input autoFocus className="prompt-input" placeholder={placeholder} value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
            if (e.key === "Escape") onCancel();
          }} />
        {error && <div className="error-note">{error}</div>}
        {children}
        <div className="form-actions">
          <button className="btn-mini btn-primary" disabled={!!error} onClick={submit}>Aceptar</button>
          <button className="btn-mini" onClick={onCancel}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
