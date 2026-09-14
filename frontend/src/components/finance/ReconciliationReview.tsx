import { AlertCircle, Check, CheckCheck, Landmark, LoaderCircle, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../services/api";
import type { ReconciliationSuggestion } from "../../types";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Feedback } from "../ui/Feedback";

const reasonLabels: Record<string, string> = {
  mesma_conta: "Mesma conta",
  mesmo_valor: "Mesmo valor",
  mesma_direcao: "Mesmo tipo",
  mesmo_dia: "Mesmo dia",
  data_proxima: "Data próxima",
  descricao_semelhante: "Descrição semelhante",
};

const confidenceLabels = { alta: "Alta confiança", media: "Média confiança", baixa: "Baixa confiança" };

interface ReconciliationReviewProps {
  onChanged: () => Promise<void>;
}

export function ReconciliationReview({ onChanged }: ReconciliationReviewProps) {
  const [suggestions, setSuggestions] = useState<ReconciliationSuggestion[]>([]);
  const [selected, setSelected] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getReconciliationSuggestions();
      setSuggestions(data);
      setSelected(Object.fromEntries(data.filter((item) => item.candidatos.length === 1).map((item) => [item.transacao_bancaria_id, item.candidatos[0].transacao_nivra_id])));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as possíveis correspondências.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const highConfidenceCount = useMemo(() => suggestions.filter((item) => (
    !item.ambigua && item.candidatos.length === 1 && item.candidatos[0].confianca === "alta"
  )).length, [suggestions]);

  async function decide(bankId: number, confirm: boolean) {
    const manualId = selected[bankId];
    if (!manualId) {
      setError("Selecione a movimentação manual correspondente antes de continuar.");
      return;
    }
    try {
      setSaving(true);
      setError("");
      if (confirm) await api.confirmSelectedBankReconciliation(bankId, manualId);
      else await api.rejectSelectedBankReconciliation(bankId, manualId);
      setMessage(confirm ? "Correspondência confirmada e contabilizada uma única vez." : "A sugestão foi rejeitada e não voltará após uma atualização comum.");
      await Promise.all([load(), onChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar a decisão.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmBatch() {
    if (!highConfidenceCount || !window.confirm(`Confirmar ${highConfidenceCount} ${highConfidenceCount === 1 ? "correspondência de alta confiança" : "correspondências de alta confiança"}?`)) return;
    try {
      setSaving(true);
      setError("");
      const result = await api.confirmHighConfidenceReconciliations();
      setMessage(`${result.confirmadas} ${result.confirmadas === 1 ? "correspondência confirmada" : "correspondências confirmadas"}.`);
      await Promise.all([load(), onChanged()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível confirmar as correspondências.");
    } finally {
      setSaving(false);
    }
  }

  if (!loading && suggestions.length === 0 && !error && !message) return null;

  return (
    <Card as="section" className="reconciliation-review" aria-label="Revisão de correspondências">
      <div className="reconciliation-review-heading">
        <div><span className="section-kicker">Revisar correspondências</span><h2>{loading ? "Procurando correspondências" : `${suggestions.length} ${suggestions.length === 1 ? "movimentação para revisar" : "movimentações para revisar"}`}</h2><p>Confirme quando o lançamento manual e o bancário representarem a mesma movimentação.</p></div>
        {highConfidenceCount > 0 ? <Button disabled={saving} onClick={() => void confirmBatch()} type="button"><CheckCheck aria-hidden="true" size={16} />Confirmar {highConfidenceCount} de alta confiança</Button> : null}
      </div>
      {error ? <Feedback>{error}</Feedback> : null}
      {message ? <Feedback tone="success">{message}</Feedback> : null}
      {loading ? <div className="reconciliation-loading"><LoaderCircle className="spin" size={20} />Analisando movimentações...</div> : null}
      {!loading ? <div className="reconciliation-list">{suggestions.map((suggestion) => (
        <article className="reconciliation-card" key={suggestion.transacao_bancaria_id}>
          <div className="reconciliation-bank-row"><span className="transaction-icon expense"><Landmark aria-hidden="true" size={17} /></span><span><strong>{suggestion.descricao}</strong><small>{suggestion.conta} · {suggestion.instituicao_nome} · {formatDate(suggestion.data)}</small></span><strong>{suggestion.direcao === "entrada" ? "+" : "−"} {formatCurrency(suggestion.valor)}</strong></div>
          {suggestion.ambigua ? <p className="reconciliation-ambiguous"><AlertCircle aria-hidden="true" size={16} />Encontramos mais de uma possível correspondência. Escolha a correta.</p> : null}
          <div className="reconciliation-candidates">{suggestion.candidatos.map((candidate) => (
            <label className="reconciliation-candidate" key={candidate.transacao_nivra_id}>
              <input checked={selected[suggestion.transacao_bancaria_id] === candidate.transacao_nivra_id} name={`match-${suggestion.transacao_bancaria_id}`} onChange={() => setSelected((current) => ({ ...current, [suggestion.transacao_bancaria_id]: candidate.transacao_nivra_id }))} type="radio" />
              <span className="reconciliation-candidate-copy"><strong>{candidate.descricao}</strong><small>Manual · {formatDate(candidate.data)} · {formatCurrency(candidate.valor)}</small><span className={`confidence-badge ${candidate.confianca}`}>{confidenceLabels[candidate.confianca]}</span><span className="reconciliation-reasons">{candidate.motivos.map((reason) => <small key={reason}>{reasonLabels[reason] ?? reason}</small>)}</span></span>
            </label>
          ))}</div>
          <div className="reconciliation-actions"><Button disabled={saving || !selected[suggestion.transacao_bancaria_id]} onClick={() => void decide(suggestion.transacao_bancaria_id, true)} type="button"><Check aria-hidden="true" size={15} />Confirmar</Button><Button disabled={saving || !selected[suggestion.transacao_bancaria_id]} onClick={() => void decide(suggestion.transacao_bancaria_id, false)} type="button" variant="secondary"><X aria-hidden="true" size={15} />Não corresponde</Button></div>
        </article>
      ))}</div> : null}
    </Card>
  );
}
