import { ArrowLeft, X } from "lucide-react";
import { useEffect } from "react";
import type { ReactNode } from "react";

interface ModalProps {
  children: ReactNode;
  onClose: () => void;
  title: string;
}

export function Modal({ children, onClose, title }: ModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("modal-open");
    };
  }, [onClose]);

  return (
    <div aria-label={title} aria-modal="true" className="modal-backdrop" role="dialog">
      <div className="modal-panel">
        <div className="modal-heading">
          <h2>{title}</h2>
          <button aria-label="Voltar e fechar" className="icon-button modal-close-button" onClick={onClose} type="button">
            <ArrowLeft aria-hidden="true" className="modal-back-icon" size={18} />
            <X aria-hidden="true" className="modal-close-icon" size={18} />
            <span className="modal-close-label">Voltar</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
