import { CalendarPlus, CalendarRange } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { InstallmentPlans } from "../components/finance/InstallmentPlans";
import { Card } from "../components/ui/Card";
import { Feedback } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/PageHeader";
import { api } from "../services/api";
import type { Account, Category } from "../types";

export function InstallmentsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReferences = useCallback(async () => {
    try {
      setLoading(true);
      const [accountData, categoryData] = await Promise.all([api.getAccounts(), api.getCategories()]);
      setAccounts(accountData);
      setCategories(categoryData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível preparar os parcelamentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadReferences(); }, [loadReferences]);

  return (
    <div className="page-stack">
      <PageHeader
        action={<Link className="button button-primary" to="/transactions?new=1#new-transaction"><CalendarPlus aria-hidden="true" size={17} />Novo parcelamento</Link>}
        description="Acompanhe, edite e consulte todas as parcelas de cada movimentação."
        eyebrow="Planejamento financeiro"
        title="Parcelamentos"
      />
      {error ? <Feedback>{error}</Feedback> : null}
      {loading ? (
        <Card aria-label="Carregando parcelamentos" className="installment-plans-card">
          <span className="skeleton skeleton-value" />
          <span className="skeleton skeleton-row" />
          <span className="skeleton skeleton-row" />
        </Card>
      ) : (
        <InstallmentPlans
          accounts={accounts}
          categories={categories}
          createHref="/transactions?new=1#new-transaction"
          onChanged={loadReferences}
          onSelectPlan={setSelectedPlanId}
          refreshKey={0}
          selectedPlanId={selectedPlanId}
        />
      )}
      <p className="installments-page-help">
        <CalendarRange aria-hidden="true" size={16} />
        <span>Para criar, selecione <strong>Parcelado</strong> no formulário de nova movimentação.</span>
      </p>
    </div>
  );
}
