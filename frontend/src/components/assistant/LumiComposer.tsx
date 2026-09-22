import { Send } from "lucide-react";
import type { ChangeEvent, FormEvent, KeyboardEvent, RefObject } from "react";

import { Button } from "../ui/Button";

interface LumiComposerProps {
  disabled: boolean;
  inputRef: RefObject<HTMLTextAreaElement>;
  maxLength: number;
  onChange: (value: string) => void;
  onSubmit: () => void;
  rateLimitSeconds: number;
  value: string;
}

export function LumiComposer({
  disabled,
  inputRef,
  maxLength,
  onChange,
  onSubmit,
  rateLimitSeconds,
  value,
}: LumiComposerProps) {
  function resizeTextarea(event: ChangeEvent<HTMLTextAreaElement>) {
    const textarea = event.currentTarget;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
    onChange(textarea.value);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!disabled && value.trim()) onSubmit();
    }
  }

  const blocked = disabled || rateLimitSeconds > 0;

  return (
    <form className="lumi-composer" onSubmit={handleSubmit}>
      <label className="sr-only" htmlFor="lumi-message-input">Pergunte à Lumi</label>
      <div className="lumi-composer-field">
        <textarea
          aria-describedby="lumi-composer-hint"
          disabled={blocked}
          id="lumi-message-input"
          maxLength={maxLength}
          onChange={resizeTextarea}
          onKeyDown={handleKeyDown}
          placeholder={rateLimitSeconds > 0 ? "Aguarde para enviar novamente" : "Pergunte sobre suas finanças..."}
          ref={inputRef}
          rows={1}
          value={value}
        />
        <Button
          aria-label="Enviar pergunta para a Lumi"
          className="lumi-send-button"
          disabled={blocked || !value.trim()}
          type="submit"
        >
          <Send aria-hidden="true" size={18} />
          <span>Enviar</span>
        </Button>
      </div>
      <div className="lumi-composer-meta" id="lumi-composer-hint">
        <span>Contexto temporário nesta página. Shift + Enter cria uma nova linha.</span>
        <span aria-label={`${value.length} de ${maxLength} caracteres`}>{value.length}/{maxLength}</span>
      </div>
    </form>
  );
}
