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

_PLUGGY_EXTERNAL_CATEGORY_PREFIXES = (
    (("salary", "retirement", "entrepreneurial_activities", "government_aid", "non_recurring_income"), "income"),
    (("same_person_transfer", "transfer", "credit_card_payment"), "transfers"),
    (("automatic_investment", "fixed_income", "mutual_funds", "variable_income", "margin", "proceeds_interests", "pension"), "investments"),
    (("late_payment", "overdraft", "interests_charged", "loan", "financing"), "loans_financing"),
    (("rent", "houseware", "urban_land", "utilities", "water", "electricity", "gas"), "housing"),
    (("groceries", "supermarket"), "groceries"),
    (("food_and_drinks", "eating_out", "food_delivery", "restaurant"), "food"),
    (("taxi", "ride_hailing", "public_transportation", "car_rental", "bicycle", "transportation"), "transport"),
    (("automotive", "gas_stations", "parking", "tolls", "vehicle_"), "vehicle"),
    (("healthcare", "dentist", "pharmacy", "optometry", "hospital", "clinics", "labs"), "health"),
    (("education", "online_courses", "university", "school", "kindergarten"), "education"),
    (("shopping", "online_shopping", "electronics", "clothing", "kids_and_toys", "bookstore", "sports_goods", "office_supplies"), "shopping"),
    (("services", "telecommunications", "internet", "mobile", "tv", "wellness", "gyms", "digital_services", "gaming", "video_streaming", "music_streaming"), "subscriptions"),
    (("leisure", "tickets", "stadiums", "landmarks", "cinema", "theater", "concerts", "gambling", "lottery", "online_bet"), "leisure"),
    (("travel", "airport", "airlines", "accommodation", "mileage_programs", "bus_tickets"), "travel"),
    (("taxes", "income_taxes", "tax_on_", "bank_fees", "account_fees", "wire_transfer_fees", "atm_fees", "legal_obligations"), "taxes"),
    (("insurance",), "insurance"),
    (("pet_supplies", "vet", "pets"), "pets"),
    (("donations", "alimony"), "donations"),
)


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
    normalized = _normalizar_categoria_externa(category_name)
    direct = _PLUGGY_EXTERNAL_CATEGORY_NAMES.get(normalized)
    if direct is not None:
        return direct
    for prefixes, nivra_key in _PLUGGY_EXTERNAL_CATEGORY_PREFIXES:
        if normalized.startswith(prefixes):
            return nivra_key
    return "other"


def is_provider_neutral_movement(
    provider: str,
    category_id: str | int | None,
    category_name: str | None,
) -> bool:
    """Reconhece movimentos que não representam receita ou despesa nova."""
    del category_id
    if provider.strip().lower() != "pluggy" or not category_name:
        return False
    normalized = _normalizar_categoria_externa(category_name)
    return normalized.startswith(("same_person_transfer", "credit_card_payment"))
