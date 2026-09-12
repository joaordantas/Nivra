import { ArrowRight, FolderCog, KeyRound, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../app/providers";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";

export function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="page-stack">
      <PageHeader description="Gerencie as preferências e a organização do seu espaço financeiro." eyebrow="Seu espaço" title="Configurações" />
      <div className="settings-grid">
        <Card className="settings-card">
          <span className="settings-icon"><FolderCog size={21} /></span>
          <div><h2>Categorias</h2><p>Crie e organize as categorias usadas nas suas movimentações.</p></div>
          <Link aria-label="Abrir categorias" className="icon-button" to="/settings/categories"><ArrowRight size={19} /></Link>
        </Card>
        <Card className="settings-card settings-card-muted">
          <span className="settings-icon"><UserRound size={21} /></span>
          <div><h2>Perfil</h2><p>{user?.email}</p><small>Mais opções de perfil serão adicionadas posteriormente.</small></div>
        </Card>
        <Card className="settings-card">
          <span className="settings-icon"><KeyRound size={21} /></span>
          <div><h2>Segurança</h2><p>Altere sua senha e encerre as outras sessões abertas.</p></div>
          <Link aria-label="Abrir segurança" className="icon-button" to="/settings/security"><ArrowRight size={19} /></Link>
        </Card>
      </div>
    </div>
  );
}
