import { Bot, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { LumiComposer } from "../components/assistant/LumiComposer";
import { LumiMessage, type LumiConversationMessage } from "../components/assistant/LumiMessage";
import { Button } from "../components/ui/Button";
import { Feedback } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/PageHeader";
import { ApiError, api } from "../services/api";
import type { LumiActionConfirmationResponse, LumiActionProposal, LumiHistoryMessage } from "../types";

const MAX_MESSAGE_LENGTH = 2_000;
const MAX_HISTORY_MESSAGES = 6;
const MAX_HISTORY_TOTAL_CHARS = 12_000;
const SUGGESTIONS = [
  "Quanto eu gastei este mês?",
  "Como estou em relação ao mês passado?",
  "Quais foram meus maiores gastos?",
  "Tenho alguma cobrança recorrente próxima?",
  "Como estão meus cartões?",
  "Qual é minha projeção para este mês?",
];

interface LumiRequestError {
  message: string;
  retryable: boolean;
  failedMessage: string;
}

let messageSequence = 0;

function newMessage(role: LumiConversationMessage["role"], content: string, proposal?: LumiActionProposal): LumiConversationMessage {
  messageSequence += 1;
  return { id: `${role}-${messageSequence}`, role, content, proposal };
}

function buildEphemeralHistory(messages: LumiConversationMessage[]): LumiHistoryMessage[] {
  const completeTurns: LumiHistoryMessage[][] = [];
  for (let index = 0; index < messages.length - 1; index += 1) {
    const userMessage = messages[index];
    const assistantMessage = messages[index + 1];
    if (userMessage.role === "user" && assistantMessage.role === "assistant") {
      completeTurns.push([
        { role: "user", content: userMessage.content },
        { role: "assistant", content: assistantMessage.content },
      ]);
      index += 1;
    }
  }

  const selected: LumiHistoryMessage[] = [];
  let totalChars = 0;
  for (let index = completeTurns.length - 1; index >= 0; index -= 1) {
    const turn = completeTurns[index];
    const turnChars = turn.reduce((total, item) => total + item.content.length, 0);
    if (selected.length + turn.length > MAX_HISTORY_MESSAGES) break;
    if (totalChars + turnChars > MAX_HISTORY_TOTAL_CHARS) break;
    selected.unshift(...turn);
    totalChars += turnChars;
  }
  return selected;
}

function friendlyError(error: unknown, failedMessage: string): LumiRequestError & { retryAfter: number } {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return { message: "Sua sessão expirou. Entre novamente para conversar com a Lumi.", retryable: false, failedMessage, retryAfter: 0 };
    }
    if (error.status === 403) {
      return { message: "Não foi possível validar a segurança desta solicitação. Atualize a página e tente novamente.", retryable: false, failedMessage, retryAfter: 0 };
    }
    if (error.status === 429) {
      return {
        message: "Você atingiu o limite temporário da Lumi. Aguarde um pouco antes de enviar outra pergunta.",
        retryable: true,
        failedMessage,
        retryAfter: error.retryAfterSeconds ?? 60,
      };
    }
    if (error.status === 409 || error.status === 410) {
      return { message: "Esta proposta mudou, expirou ou já foi usada. Crie uma nova proposta para continuar.", retryable: false, failedMessage, retryAfter: 0 };
    }
    if (error.status === 503) {
      return { message: "A Lumi está temporariamente indisponível. Você pode tentar esta pergunta novamente em instantes.", retryable: true, failedMessage, retryAfter: 0 };
    }
    if (error.status === 504) {
      return { message: "A análise demorou mais que o esperado. Tente novamente quando quiser.", retryable: true, failedMessage, retryAfter: 0 };
    }
    if (error.status >= 500) {
      return { message: "A Lumi encontrou uma indisponibilidade temporária. Tente novamente em instantes.", retryable: true, failedMessage, retryAfter: 0 };
    }
    return { message: "Não foi possível concluir esta pergunta. Revise a mensagem e tente novamente.", retryable: false, failedMessage, retryAfter: 0 };
  }

  return {
    message: "Não foi possível conectar à Lumi. Verifique sua conexão e tente novamente.",
    retryable: true,
    failedMessage,
    retryAfter: 0,
  };
}

export function LumiPage() {
  const [messages, setMessages] = useState<LumiConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [requestError, setRequestError] = useState<LumiRequestError | null>(null);
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0);
  const [actionsEnabled, setActionsEnabled] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);
  const nearBottomRef = useRef(true);
  const sendingRef = useRef(false);

  useEffect(() => () => {
    mountedRef.current = false;
    abortControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (rateLimitSeconds <= 0) return;
    const timer = window.setInterval(() => {
      setRateLimitSeconds((current) => Math.max(0, current - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [rateLimitSeconds > 0]);

  useEffect(() => {
    if (!nearBottomRef.current) return;
    const container = messagesRef.current;
    if (container) container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [messages, isSending, requestError]);

  function handleMessagesScroll() {
    const container = messagesRef.current;
    if (!container) return;
    nearBottomRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < 96;
  }

  async function sendMessage(rawMessage: string, appendUserMessage = true) {
    const message = rawMessage.trim();
    if (!message || message.length > MAX_MESSAGE_LENGTH || sendingRef.current || rateLimitSeconds > 0) return;

    sendingRef.current = true;
    nearBottomRef.current = true;
    if (appendUserMessage) {
      setMessages((current) => [...current, newMessage("user", message)]);
      setInput("");
      if (inputRef.current) inputRef.current.style.height = "auto";
    }
    setRequestError(null);
    setIsSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const history = buildEphemeralHistory(messages);
      const response = await api.sendLumiMessage(message, history, controller.signal);
      if (!mountedRef.current) return;
      if (response.type === "action_proposal" && response.execution_enabled) setActionsEnabled(true);
      setMessages((current) => [...current, newMessage("assistant", response.message, response.type === "action_proposal" ? response : undefined)]);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (!mountedRef.current) return;
      const handled = friendlyError(error, message);
      setRequestError(handled);
      setRateLimitSeconds(handled.retryAfter);
    } finally {
      if (abortControllerRef.current === controller) abortControllerRef.current = null;
      if (!mountedRef.current) return;
      sendingRef.current = false;
      setIsSending(false);
      window.requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function submitCurrentMessage() {
    void sendMessage(input);
  }

  function retryFailedMessage() {
    if (!requestError || !requestError.retryable || rateLimitSeconds > 0) return;
    void sendMessage(requestError.failedMessage, false);
  }

  function applyConfirmation(messageId: string, result: LumiActionConfirmationResponse) {
    setMessages((current) => current.map((message) => {
      if (message.id !== messageId || !message.proposal?.confirmation) return message;
      return {
        ...message,
        content: result.message,
        pendingAction: null,
        proposal: {
          ...message.proposal,
          confirmation: { ...message.proposal.confirmation, status: result.status, expires_at: result.expires_at },
        },
      };
    }));
  }

  async function handleProposalOperation(messageId: string, confirmationId: string, operation: "confirm" | "cancel") {
    setMessages((current) => current.map((message) => message.id === messageId ? { ...message, pendingAction: operation } : message));
    try {
      const result = operation === "confirm"
        ? await api.confirmLumiAction(confirmationId)
        : await api.cancelLumiAction(confirmationId);
      if (mountedRef.current) {
        applyConfirmation(messageId, result);
      }
    } catch (error) {
      if (!mountedRef.current) return;
      setMessages((current) => current.map((message) => message.id === messageId ? { ...message, pendingAction: null } : message));
      setRequestError(friendlyError(error, ""));
    }
  }

  return (
    <div className="lumi-page">
      <PageHeader
        action={<span className="lumi-read-only-badge"><ShieldCheck aria-hidden="true" size={15} />{actionsEnabled ? "Lumi • Alpha · ações com confirmação" : "Lumi • Alpha · consultas"}</span>}
        description="A Lumi está em desenvolvimento. Consulte seus dados financeiros; ações podem estar desabilitadas e, quando disponíveis, exigem confirmação explícita. O contexto da conversa é temporário."
        eyebrow="Assistente financeira"
        title="Lumi"
      />

      <section className="lumi-shell" aria-label="Conversa com a Lumi">
        <div
          aria-live="polite"
          aria-relevant="additions text"
          className="lumi-messages"
          onScroll={handleMessagesScroll}
          ref={messagesRef}
          role="log"
        >
          {messages.length === 0 ? (
            <div className="lumi-empty-state">
              <div className="lumi-empty-icon" aria-hidden="true"><Sparkles size={25} /></div>
              <h2>O que você quer entender hoje?</h2>
              <p>
                A Lumi consulta gastos, receitas, evolução financeira, maiores despesas, cartões,
                projeções, recorrências e movimentações fora do padrão.
              </p>
              <span>O contexto da conversa desaparece ao recarregar a página. A disponibilidade de ações depende da configuração do ambiente.</span>
              <div className="lumi-suggestions" aria-label="Sugestões de perguntas">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    disabled={isSending || rateLimitSeconds > 0}
                    key={suggestion}
                    onClick={() => void sendMessage(suggestion)}
                    type="button"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <LumiMessage
                key={message.id}
                message={message}
                onCancelProposal={(messageId, confirmationId) => void handleProposalOperation(messageId, confirmationId, "cancel")}
                onConfirmProposal={(messageId, confirmationId) => void handleProposalOperation(messageId, confirmationId, "confirm")}
              />
            ))
          )}

          {isSending ? (
            <div className="lumi-processing" role="status">
              <span className="lumi-processing-icon" aria-hidden="true"><Bot size={17} /></span>
              <span><i /><i /><i /></span>
              <span>Analisando suas finanças...</span>
            </div>
          ) : null}
        </div>

        {requestError ? (
          <div className="lumi-error-area">
            <Feedback>{requestError.message}</Feedback>
            {requestError.retryable ? (
              <Button
                disabled={isSending || rateLimitSeconds > 0}
                onClick={retryFailedMessage}
                type="button"
                variant="secondary"
              >
                <RefreshCw aria-hidden="true" size={16} />
                {rateLimitSeconds > 0 ? `Tentar em ${rateLimitSeconds}s` : "Tentar novamente"}
              </Button>
            ) : null}
          </div>
        ) : null}

        <LumiComposer
          disabled={isSending}
          inputRef={inputRef}
          maxLength={MAX_MESSAGE_LENGTH}
          onChange={setInput}
          onSubmit={submitCurrentMessage}
          rateLimitSeconds={rateLimitSeconds}
          value={input}
        />
      </section>
    </div>
  );
}
