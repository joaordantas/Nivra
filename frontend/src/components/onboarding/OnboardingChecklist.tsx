import { CheckCircle2, X } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";

interface Props {
  userId: number;
}

export function OnboardingChecklist({ userId }: Props) {
  const storageKey = `nivra:onboarding:v1:${userId}`;
  const [visible, setVisible] = useState(() => window.localStorage.getItem(storageKey) !== "done");
  if (!visible) return null;

  function dismiss() {
    window.localStorage.setItem(storageKey, "done");
    setVisible(false);
  }

  return (
    <section aria-labelledby="onboarding-title" className="onboarding-card">
      <div>
        <span className="section-kicker">Primeiros passos</span>
        <h2 id="onboarding-title">Prepare sua visão financeira</h2>
        <p>Conclua estes passos com dados de demonstração ou informações que você escolher registrar.</p>
      </div>
      <ol>
        <li><CheckCircle2 aria-hidden="true" size={18} /><Link to="/accounts">Cadastre ou conecte uma conta</Link></li>
        <li><CheckCircle2 aria-hidden="true" size={18} /><Link to="/transactions?new=1#new-transaction">Registre a primeira movimentação</Link></li>
        <li><CheckCircle2 aria-hidden="true" size={18} /><Link to="/budgets">Defina um orçamento mensal</Link></li>
      </ol>
      <button aria-label="Concluir onboarding" className="icon-button onboarding-close" onClick={dismiss} type="button"><X aria-hidden="true" size={17} /></button>
    </section>
  );
}
