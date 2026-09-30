import { Bot, UserRound } from "lucide-react";
import type { LumiActionProposal } from "../../types";
import { LumiActionProposalCard } from "./LumiActionProposalCard";

export interface LumiConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposal?: LumiActionProposal;
  pendingAction?: "confirm" | "cancel" | null;
  quickActions?: string[];
}

interface LumiMessageProps {
  message: LumiConversationMessage;
  onCancelProposal: (messageId: string, confirmationId: string) => void;
  onConfirmProposal: (messageId: string, confirmationId: string) => void;
  onQuickAction: (prompt: string) => void;
}

function MessageBody({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).filter(Boolean);
  return <div className="lumi-message-body">{blocks.map((block, blockIndex) => {
    const lines = block.split("\n").filter(Boolean);
    const isList = lines.every((line) => /^[-•]\s+/.test(line.trim()));
    if (isList) return <ul key={blockIndex}>{lines.map((line, index) => <li key={index}>{line.replace(/^[-•]\s+/, "")}</li>)}</ul>;
    return <p key={blockIndex}>{block}</p>;
  })}</div>;
}

export function LumiMessage({ message, onCancelProposal, onConfirmProposal, onQuickAction }: LumiMessageProps) {
  const isAssistant = message.role === "assistant";
  const label = isAssistant ? "Lumi" : "Você";
  const Icon = isAssistant ? Bot : UserRound;

  return (
    <article className={`lumi-message lumi-message-${message.role}`} aria-label={`Mensagem de ${label}`}>
      <div className="lumi-message-avatar" aria-hidden="true">
        <Icon size={17} />
      </div>
      <div className="lumi-message-content">
        <strong>{label}{isAssistant ? <span className="lumi-alpha-label"> · Alpha</span> : null}</strong>
        <MessageBody content={message.content} />
        {isAssistant && message.proposal ? (
          <LumiActionProposalCard
            onCancel={(confirmationId) => onCancelProposal(message.id, confirmationId)}
            onConfirm={(confirmationId) => onConfirmProposal(message.id, confirmationId)}
            pendingAction={message.pendingAction ?? null}
            proposal={message.proposal}
          />
        ) : null}
        {isAssistant && !message.proposal && message.quickActions?.length ? (
          <div className="lumi-quick-actions" aria-label="Sugestões para continuar">
            {message.quickActions.map((action) => <button key={action} onClick={() => onQuickAction(action)} type="button">{action}</button>)}
          </div>
        ) : null}
      </div>
    </article>
  );
}
