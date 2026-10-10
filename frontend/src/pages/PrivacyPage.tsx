import { Link } from "react-router-dom";

export function PrivacyPage() {
  return (
    <main className="legal-page">
      <article className="legal-document">
        <Link className="auth-back-link" to="/login">← Voltar para a Nivra</Link>
        <span className="section-kicker">Nivra Alpha · vigente em 10/10/2026</span>
        <h1>Política de Privacidade</h1>
        <p>A Nivra usa dados fornecidos por você para organizar finanças pessoais, autenticar sua conta, oferecer recursos escolhidos e proteger a operação do serviço.</p>
        <h2>Dados tratados</h2>
        <p>Podem ser tratados dados de cadastro, sessões, contas financeiras, movimentações, categorias, cartões, orçamentos, metas, preferências e dados de integrações que você autorizar. Senhas são armazenadas somente como hash seguro; tokens e segredos não são exibidos em logs.</p>
        <h2>Finalidades e base operacional</h2>
        <p>Os dados são usados para executar as funções solicitadas, prevenir abuso, manter segurança, produzir notificações internas e permitir suporte e diagnóstico. A Nivra não vende dados pessoais.</p>
        <h2>Retenção</h2>
        <p>Notificações lidas podem ser removidas 180 dias após a leitura; não lidas são preservadas. Histórico terminal de jobs pode ser removido após 180 dias, preservando a última execução por tipo. Logs sanitizados têm meta de 30 dias. Dados financeiros e preferências permanecem enquanto necessários à conta ou até solicitação de exclusão aplicável.</p>
        <h2>Compartilhamento e infraestrutura</h2>
        <p>O serviço pode usar provedores de hospedagem, banco de dados, e-mail e integrações financeiras para executar funcionalidades. Cada integração só é usada quando configurada e autorizada no ambiente correspondente.</p>
        <h2>Seus direitos</h2>
        <p>Você pode solicitar confirmação de tratamento, acesso, correção, portabilidade quando aplicável, revisão de preferências e exclusão, observadas obrigações legais e técnicas. Durante o piloto, use o canal oficial pelo qual recebeu acesso à Nivra.</p>
        <h2>Segurança e incidentes</h2>
        <p>A Nivra aplica sessões server-side, cookies protegidos, CSRF, isolamento por usuário, rate limiting e logs sanitizados. Nenhum sistema é infalível; incidentes confirmados serão tratados e comunicados conforme o risco e a legislação aplicável.</p>
        <p className="legal-note">Esta versão operacional atende ao piloto Alpha e deve receber revisão jurídica antes de abertura pública ampla.</p>
      </article>
    </main>
  );
}
