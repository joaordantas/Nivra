import { ArrowLeft, FolderPlus, LockKeyhole, Pencil, Tags, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "../../services/api";
import { useAuth } from "../../app/providers";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Feedback } from "../../components/ui/Feedback";
import { PageHeader } from "../../components/ui/PageHeader";
import type { Category } from "../../types";

export function CategoriesPage() {
  const { user } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    if (!user) return;
    try {
      setLoading(true);
      setCategories(await api.getCategories());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar suas categorias.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [user?.id]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || !newCategory.trim()) return;
    try {
      await api.createCategory(newCategory);
      setNewCategory("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar a categoria.");
    }
  }

  async function handleSave(categoryId: number) {
    if (!user) return;
    try {
      await api.updateCategory(categoryId, editingName);
      setEditingId(null);
      setEditingName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar a categoria.");
    }
  }

  async function handleDelete(categoryId: number) {
    if (!user) return;
    try {
      await api.deleteCategory(categoryId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível remover a categoria.");
    }
  }

  return (
    <div className="page-stack">
      <Link className="back-link" to="/settings"><ArrowLeft size={17} />Configurações</Link>
      <PageHeader description="Use categorias para entender para onde seu dinheiro está indo." eyebrow="Configurações" title="Categorias" />
      {error ? <Feedback>{error}</Feedback> : null}

      <div className="settings-detail-grid">
        <Card as="section">
          <div className="card-heading"><span className="section-kicker">Organização</span><h2>Nova categoria</h2></div>
          <form className="form-grid" onSubmit={handleCreate}>
            <label>Nome<input onChange={(event) => setNewCategory(event.target.value)} placeholder="Ex.: Alimentação" value={newCategory} /></label>
            <Button disabled={!newCategory.trim()} type="submit"><FolderPlus size={18} />Criar categoria</Button>
          </form>
        </Card>

        <Card as="section" className="category-list-card">
          <div className="card-heading card-heading-row"><div><span className="section-kicker">Categorias</span><h2>Suas categorias</h2></div><span className="count-badge">{categories.length}</span></div>
          {loading ? (
            <div className="category-list">{[1, 2, 3].map((item) => <span className="skeleton skeleton-row" key={item} />)}</div>
          ) : categories.length === 0 ? (
            <EmptyState description="Crie categorias para separar seus gastos e receitas." icon={Tags} title="Nenhuma categoria criada" />
          ) : (
            <div className="category-list">
              {categories.map((category) => (
                <div className="category-row" key={category.id}>
                  <span className="category-symbol"><Tags size={17} /></span>
                  {editingId === category.id ? (
                    <input autoFocus onChange={(event) => setEditingName(event.target.value)} value={editingName} />
                  ) : <strong>{category.nome}</strong>}
                  <div className="row-actions">
                    {editingId === category.id ? (
                      <><Button onClick={() => void handleSave(category.id)} type="button" variant="secondary">Salvar</Button><button aria-label="Cancelar edição" className="icon-button" onClick={() => setEditingId(null)} type="button"><X size={17} /></button></>
                    ) : (
                      <button aria-label={`Editar ${category.nome}`} className="icon-button" onClick={() => { setEditingId(category.id); setEditingName(category.nome); }} type="button"><Pencil size={17} /></button>
                    )}
                    {category.padrao ? (
                      <span aria-label={`${category.nome} é uma categoria padrão`} className="category-system-lock" title="Categoria padrão"><LockKeyhole size={16} /></span>
                    ) : <button aria-label={`Excluir ${category.nome}`} className="icon-button icon-button-danger" onClick={() => void handleDelete(category.id)} type="button"><Trash2 size={17} /></button>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
