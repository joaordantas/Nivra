import { Bot, UserRound } from "lucide-react";
import type { LumiActionProposal } from "../../types";
import { LumiActionProposalCard } from "./LumiActionProposalCard";

export interface LumiConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposal?: LumiActionProposal;
  pendingAction?: "confirm" | "cancel" | null;
}

interface LumiMessageProps {
  message: LumiConversationMessage;
  onCancelProposal: (messageId: string, confirmationId: string) => void;
  onConfirmProposal: (messageId: string, confirmationId: string) => void;
}

export function LumiMessage({ message, onCancelProposal, onConfirmProposal }: LumiMessageProps) {
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
        <p>{message.content}</p>
        {isAssistant && message.proposal ? (
          <LumiActionProposalCard
            onCancel={(confirmationId) => onCancelProposal(message.id, confirmationId)}
            onConfirm={(confirmationId) => onConfirmProposal(message.id, confirmationId)}
            pendingAction={message.pendingAction ?? null}
            proposal={message.proposal}
          />
        ) : null}
      </div>
    </article>
  );
}
