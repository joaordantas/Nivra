from __future__ import annotations

import re
import unicodedata


DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("income", "Renda"),
    ("transfers", "Transferências"),
    ("investments", "Investimentos"),
    ("loans_financing", "Empréstimos e Financiamentos"),
    ("housing", "Moradia"),
    ("groceries", "Mercado"),
    ("food", "Alimentação"),
    ("transport", "Transporte"),
    ("vehicle", "Veículo"),
    ("health", "Saúde"),
    ("education", "Educação"),
    ("shopping", "Compras"),
    ("subscriptions", "Serviços e Assinaturas"),
    ("leisure", "Lazer"),
    ("travel", "Viagens"),
    ("taxes", "Impostos e Taxas"),
    ("insurance", "Seguros"),
    ("pets", "Pets"),
    ("donations", "Doações"),
    ("other", "Outros"),
)

DEFAULT_CATEGORY_KEYS = frozenset(key for key, _ in DEFAULT_CATEGORIES)


def _normalizar_categoria_externa(value: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem_acentos.lower()).strip("_")


# Mapeamentos de nomes são exclusivamente do provider. Nomes personalizados da
# categoria do usuário não participam da decisão de categorização.
_PLUGGY_EXTERNAL_CATEGORY_NAMES = {
    "income": "income",
    "salary": "income",
    "transfer": "transfers",
    "transfers": "transfers",
    "investment": "investments",
    "investments": "investments",
    "loan": "loans_financing",
    "loans": "loans_financing",
    "housing": "housing",
    "rent": "housing",
    "groceries": "groceries",
    "supermarket": "groceries",
    "food": "food",
    "restaurant": "food",
    "transport": "transport",
    "vehicle": "vehicle",
    "health": "health",
    "education": "education",
    "shopping": "shopping",
    "subscriptions": "subscriptions",
    "leisure": "leisure",
    "travel": "travel",
    "taxes": "taxes",
    "insurance": "insurance",
    "pets": "pets",
    "donations": "donations",
}


def map_provider_category(
    provider: str,
    category_id: str | int | None,
    category_name: str | None,
) -> str:
    """Converte categoria externa em uma chave interna estável da Nivra.

    IDs específicos poderão ser acrescentados quando a Etapa 2C conhecer os
    identificadores estáveis do provider. Até lá, a única leitura textual é do
    nome retornado pelo provider, nunca de um nome que o usuário editou.
    """
    del category_id  # Reservado para mapeamentos de IDs estáveis do provider.
    if provider.strip().lower() != "pluggy" or not category_name:
        return "other"
    return _PLUGGY_EXTERNAL_CATEGORY_NAMES.get(
        _normalizar_categoria_externa(category_name),
        "other",
    )
