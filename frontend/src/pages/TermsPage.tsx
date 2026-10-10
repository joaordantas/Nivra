import { Link } from "react-router-dom";

export function TermsPage() {
  return (
    <main className="legal-page">
      <article className="legal-document">
        <Link className="auth-back-link" to="/login">← Voltar para a Nivra</Link>
        <span className="section-kicker">Nivra Alpha · vigente em 10/10/2026</span>
        <h1>Termos de Uso</h1>
        <p>Ao usar a Nivra, você concorda em fornecer informações legítimas, proteger suas credenciais e utilizar o serviço apenas para finalidades lícitas.</p>
        <h2>Serviço Alpha</h2>
        <p>A Nivra está em evolução. Recursos podem mudar, apresentar indisponibilidade ou exigir nova validação. O serviço não substitui aconselhamento contábil, jurídico, fiscal ou de investimentos.</p>
        <h2>Responsabilidade do usuário</h2>
        <p>Você é responsável por revisar registros, classificações, alertas e decisões financeiras. Não compartilhe sua senha, tokens ou sessão e comunique suspeitas de acesso indevido pelo canal oficial do piloto.</p>
        <h2>Integrações</h2>
        <p>Conexões externas seguem também os termos dos respectivos provedores. Durante o piloto, integrações financeiras podem operar apenas em Sandbox e não devem ser tratadas como conexão bancária de produção.</p>
        <h2>Disponibilidade e alterações</h2>
        <p>Podemos suspender recursos para segurança, manutenção ou correção. Mudanças relevantes nestes termos serão indicadas por nova data de vigência.</p>
        <h2>Encerramento</h2>
        <p>O acesso pode ser encerrado por solicitação do usuário, término do piloto, violação destes termos ou risco à segurança. A exclusão de dados seguirá a política de privacidade e as obrigações aplicáveis.</p>
        <p className="legal-note">Estes termos disciplinam o piloto Alpha e devem receber revisão jurídica antes de disponibilização pública ampla.</p>
      </article>
    </main>
  );
}
