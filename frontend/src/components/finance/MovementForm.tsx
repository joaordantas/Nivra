import { ArrowDownLeft, ArrowRight, ArrowRightLeft, ArrowUpRight, CalendarRange, FolderPlus } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import type { Account, Category, MovementFormValues, MovementType } from "../../types";
import { Button } from "../ui/Button";

interface MovementFormProps {
  accounts: Account[];
  autoFocus?: boolean;
  categories: Category[];
  initialValues: MovementFormValues;
  mode: "create" | "edit";
  onCreateCategory: (name: string) => Promise<Category>;
  onSubmit: (values: MovementFormValues) => Promise<void>;
  saving: boolean;
}

const typeOptions: Array<{ value: MovementType; label: string; icon: typeof ArrowUpRight }> = [
  { value: "saida", label: "Despesa", icon: ArrowUpRight },
  { value: "entrada", label: "Receita", icon: ArrowDownLeft },
  { value: "transferencia", label: "Transferência", icon: ArrowRightLeft },
];

export function MovementForm({
  accounts,
  autoFocus = false,
  categories,
  initialValues,
  mode,
  onCreateCategory,
  onSubmit,
  saving,
}: MovementFormProps) {
  const [values, setValues] = useState(initialValues);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [categoryName, setCategoryName] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [categoryError, setCategoryError] = useState("");

  const availableTypes = mode === "create"
    ? typeOptions
    : typeOptions.filter((option) => (
      initialValues.tipo === "transferencia"
        ? option.value === "transferencia"
        : option.value !== "transferencia"
    ));
  const isTransfer = values.tipo === "transferencia";
  const isInstallment = mode === "create" && !isTransfer && values.forma === "parcelado";
  const totalCents = Math.round(values.valor * 100);
  const installmentCents = values.quantidadeParcelas > 0
    ? Math.floor(totalCents / values.quantidadeParcelas)
    : 0;
  const hasUnevenInstallments = values.quantidadeParcelas > 0
    && totalCents % values.quantidadeParcelas !== 0;
  const canSubmit = values.valor > 0
    && values.descricao.trim().length > 0
    && Boolean(values.data)
    && (isTransfer
      ? values.contaOrigemId > 0
        && values.contaDestinoId > 0
        && values.contaOrigemId !== values.contaDestinoId
      : Boolean(values.contaId))
    && (!isInstallment || values.quantidadeParcelas >= 2);

  function update<K extends keyof MovementFormValues>(field: K, value: MovementFormValues[K]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function selectType(tipo: MovementType) {
    const primaryAccount = accounts.find((account) => account.principal) ?? accounts[0];
    const secondAccount = accounts.find((account) => account.id !== primaryAccount?.id);
    setValues((current) => ({
      ...current,
      tipo,
      forma: tipo === "transferencia" ? "avista" : current.forma,
      contaId: tipo === "transferencia" ? null : current.contaId ?? primaryAccount?.id ?? null,
      contaOrigemId: current.contaOrigemId || primaryAccount?.id || 0,
      contaDestinoId: current.contaDestinoId || secondAccount?.id || 0,
    }));
  }

  async function handleCreateCategory() {
    if (!categoryName.trim()) return;
    try {
      setCreatingCategory(true);
      const category = await onCreateCategory(categoryName);
      update("categoriaId", category.id);
      setCategoryName("");
      setShowCategoryForm(false);
      setCategoryError("");
    } catch (error) {
      setCategoryError(error instanceof Error ? error.message : "Não foi possível criar a categoria.");
    } finally {
      setCreatingCategory(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) await onSubmit(values);
  }

  return (
    <form className="form-grid movement-form" onSubmit={handleSubmit}>
      <div className={`segmented-control movement-type-control ${availableTypes.length === 1 ? "single-option" : ""}`} aria-label="Tipo de movimentação">
        {availableTypes.map((option) => {
          const Icon = option.icon;
          return (
            <button className={values.tipo === option.value ? "is-active" : ""} key={option.value} onClick={() => selectType(option.value)} type="button">
              <Icon aria-hidden="true" size={17} />{option.label}
            </button>
          );
        })}
      </div>

      <label className="amount-field">
        <span>Valor</span>
        <div><span>R$</span><input autoFocus={autoFocus} min="0.01" onChange={(event) => update("valor", Number(event.target.value))} step="0.01" type="number" value={values.valor || ""} /></div>
      </label>

      <label>
        Descrição
        <input maxLength={255} onChange={(event) => update("descricao", event.target.value)} placeholder={isTransfer ? "Ex.: Reserva do mês" : "Ex.: Mercado, salário, academia"} value={values.descricao} />
      </label>

      {mode === "create" && !isTransfer ? (
        <fieldset className="installment-choice">
          <legend>Forma</legend>
          <div className="segmented-control installment-type-control" aria-label="Forma da movimentação">
            <button className={values.forma === "avista" ? "is-active" : ""} onClick={() => update("forma", "avista")} type="button">À vista</button>
            <button className={values.forma === "parcelado" ? "is-active" : ""} onClick={() => update("forma", "parcelado")} type="button"><CalendarRange aria-hidden="true" size={16} />Parcelado</button>
          </div>
        </fieldset>
      ) : null}

      {isInstallment ? (
        <div className="installment-fields">
          <label>
            Quantidade de parcelas
            <input min="2" onChange={(event) => update("quantidadeParcelas", Number(event.target.value))} step="1" type="number" value={values.quantidadeParcelas} />
          </label>
          <div className="installment-preview" role="status">
            <CalendarRange aria-hidden="true" size={18} />
            <span>
              <strong>{values.quantidadeParcelas >= 2 ? `${values.quantidadeParcelas} parcelas` : "Informe ao menos 2 parcelas"}</strong>
              {values.valor > 0 && values.quantidadeParcelas >= 2 ? (
                <small>{hasUnevenInstallments ? `Total ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(values.valor)} · os centavos serão distribuídos pelo backend` : `${values.quantidadeParcelas}x de ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(installmentCents / 100)} por mês`}</small>
              ) : <small>A primeira parcela usará a data informada abaixo.</small>}
            </span>
          </div>
        </div>
      ) : null}

      {isTransfer ? (
        accounts.length < 2 ? (
          <div className="inline-empty">
            <ArrowRightLeft aria-hidden="true" size={20} />
            <p>Você precisa de duas contas ativas. <Link to="/accounts">Gerenciar contas</Link></p>
          </div>
        ) : (
          <div className="transfer-accounts">
            <label>De<select onChange={(event) => update("contaOrigemId", Number(event.target.value))} value={values.contaOrigemId}>{accounts.map((account) => <option disabled={account.id === values.contaDestinoId} key={account.id} value={account.id}>{account.nome}</option>)}</select></label>
            <ArrowRight aria-hidden="true" size={20} />
            <label>Para<select onChange={(event) => update("contaDestinoId", Number(event.target.value))} value={values.contaDestinoId}>{accounts.map((account) => <option disabled={account.id === values.contaOrigemId} key={account.id} value={account.id}>{account.nome}</option>)}</select></label>
          </div>
        )
      ) : (
        <>
          <label>
            Categoria
            <select onChange={(event) => update("categoriaId", event.target.value ? Number(event.target.value) : null)} value={values.categoriaId ?? ""}>
              <option value="">Sem categoria</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.nome}</option>)}
            </select>
          </label>
          {showCategoryForm ? (
            <div className="inline-category-form">
              <input aria-label="Nome da nova categoria" onChange={(event) => setCategoryName(event.target.value)} placeholder="Nome da categoria" value={categoryName} />
              <Button disabled={creatingCategory || !categoryName.trim()} onClick={() => void handleCreateCategory()} type="button" variant="secondary">Salvar</Button>
              <button className="text-button" onClick={() => setShowCategoryForm(false)} type="button">Cancelar</button>
              {categoryError ? <small className="field-error">{categoryError}</small> : null}
            </div>
          ) : (
            <button className="text-button add-category-button" onClick={() => setShowCategoryForm(true)} type="button"><FolderPlus size={15} />Criar categoria</button>
          )}
          <label>
            Conta
            <select onChange={(event) => update("contaId", event.target.value ? Number(event.target.value) : null)} value={values.contaId ?? ""}>
              <option value="">Selecione uma conta</option>
              {accounts.map((account) => <option key={account.id} value={account.id}>{account.nome}</option>)}
            </select>
          </label>
          {accounts.length === 0 ? <small className="field-hint">Adicione uma conta antes de registrar movimentações.</small> : null}
        </>
      )}

      <label>
        Data
        <input onChange={(event) => update("data", event.target.value)} type="date" value={values.data} />
      </label>

      <Button disabled={saving || !canSubmit} type="submit">
        {saving ? "Salvando..." : mode === "edit" ? "Salvar alterações" : isTransfer ? "Transferir" : isInstallment ? "Criar parcelamento" : "Adicionar movimentação"}
      </Button>
    </form>
  );
}
