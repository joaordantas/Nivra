import { CheckCircle2, Circle, KeyRound, Landmark, RefreshCw, WalletCards } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../ui/Button";

interface OpenFinanceDemoGuideProps {
  hasConnection: boolean;
  hasLinkedAccount: boolean;
  hasTransactions: boolean;
  isConnecting: boolean;
  onConnect: () => void;
}

interface DemoStepProps {
  complete: boolean;
  description: string;
  title: string;
}

function DemoStep({ complete, description, title }: DemoStepProps) {
  return (
    <li className={complete ? "is-complete" : ""}>
      {complete ? <CheckCircle2 aria-hidden="true" size={17} /> : <Circle aria-hidden="true" size={17} />}
      <span><strong>{title}</strong><small>{description}</small></span>
    </li>
  );
}

export function OpenFinanceDemoGuide({ hasConnection, hasLinkedAccount, hasTransactions, isConnecting, onConnect }: OpenFinanceDemoGuideProps) {
  return (
    <section className="open-finance-demo-guide" aria-label="Guia de demonstração Open Finance">
      <div className="open-finance-demo-guide-heading">
        <div><span className="section-kicker">Primeiro teste</span><h3>Experimente em poucos passos</h3></div>
        {!hasConnection ? <Button disabled={isConnecting} onClick={onConnect} type="button" variant="secondary"><Landmark aria-hidden="true" size={15} />Conectar banco</Button> : null}
      </div>
      <ol className="open-finance-demo-steps">
        <DemoStep complete={hasConnection} description="Escolha o Pluggy Bank no ambiente de demonstração." title="Conecte um banco de demonstração" />
        <DemoStep complete={hasTransactions} description="Use “Atualizar dados” para trazer contas, saldo e movimentações." title="Atualize os dados" />
        <DemoStep complete={hasLinkedAccount} description="Vincule uma conta importada ou crie uma conta Nivra a partir dela." title="Vincule a conta à Nivra" />
        <DemoStep complete={hasTransactions} description={hasTransactions ? "O histórico já está disponível em Transações." : "As movimentações aparecerão depois da atualização."} title="Veja suas movimentações" />
      </ol>
      {hasTransactions ? <Link className="text-link open-finance-demo-history-link" to="/transactions"><RefreshCw aria-hidden="true" size={14} />Ver histórico unificado</Link> : null}
      <details className="open-finance-demo-credentials">
        <summary><KeyRound aria-hidden="true" size={15} />Credenciais fictícias do Pluggy Bank</summary>
        <div>
          <p>Use somente estes dados de demonstração no Connect. Nunca informe credenciais bancárias reais neste ambiente.</p>
          <dl>
            <div><dt>Usuário</dt><dd>user-ok</dd></div>
            <div><dt>Senha</dt><dd>password-ok</dd></div>
            <div><dt>MFA</dt><dd>123456</dd></div>
          </dl>
        </div>
      </details>
      <p className="open-finance-demo-note"><WalletCards aria-hidden="true" size={15} />Dados, saldos e movimentações exibidos aqui são fictícios e servem apenas para teste.</p>
    </section>
  );
}
