from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from services.transacao_service import listar_transacoes_formatadas
from services.transferencia_service import listar_transferencias_formatadas


MovementTypeFilter = Literal["entrada", "saida", "transferencia"]
MovementOriginFilter = Literal["manual", "open_finance", "conciliada"]


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _transaction_item(transaction: dict) -> dict:
    return {"kind": "transaction", "transaction": transaction}


def _transfer_item(transfer: dict) -> dict:
    return {"kind": "transfer", "transfer": transfer}


def _item_date(item: dict) -> str:
    payload = item["transaction"] if item["kind"] == "transaction" else item["transfer"]
    return str(payload["data"])


def _item_id(item: dict) -> int:
    payload = item["transaction"] if item["kind"] == "transaction" else item["transfer"]
    return int(payload["id"])


def _matches(
    item: dict,
    *,
    search: str | None,
    movement_type: MovementTypeFilter | None,
    account_id: int | None,
    category_id: int | None,
    origin: MovementOriginFilter | None,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    if item["kind"] == "transaction":
        payload = item["transaction"]
        searchable = (
            payload.get("comentario") or "",
            payload.get("categoria") or "",
            payload.get("conta") or "",
        )
        item_type = payload["tipo"]
        account_matches = account_id is None or payload.get("conta_id") == account_id
        category_matches = category_id is None or payload.get("categoria_id") == category_id
        if origin == "manual":
            origin_matches = payload.get("origem") == "manual" and not payload.get("conciliada_com_banco")
        elif origin == "open_finance":
            origin_matches = payload.get("origem") == "open_finance"
        elif origin == "conciliada":
            origin_matches = bool(payload.get("conciliada_com_banco"))
        else:
            origin_matches = True
    else:
        payload = item["transfer"]
        searchable = (
            payload.get("descricao") or "",
            payload.get("conta_origem") or "",
            payload.get("conta_destino") or "",
        )
        item_type = "transferencia"
        account_matches = account_id is None or account_id in {
            payload.get("conta_origem_id"), payload.get("conta_destino_id")
        }
        category_matches = category_id is None
        origin_matches = origin in {None, "manual"}

    normalized_search = (search or "").strip().casefold()
    search_matches = not normalized_search or any(
        normalized_search in str(value).casefold() for value in searchable
    )
    item_day = date.fromisoformat(_item_date(item))
    return (
        search_matches
        and (movement_type is None or item_type == movement_type)
        and account_matches
        and category_matches
        and origin_matches
        and (start_date is None or item_day >= start_date)
        and (end_date is None or item_day <= end_date)
    )


def list_movement_page(
    user_id: int,
    *,
    search: str | None = None,
    movement_type: MovementTypeFilter | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    origin: MovementOriginFilter | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("A data inicial não pode ser posterior à data final.")

    items = [
        *(_transaction_item(item) for item in listar_transacoes_formatadas(user_id)),
        *(_transfer_item(item) for item in listar_transferencias_formatadas(user_id)),
    ]
    filtered = [
        item for item in items
        if _matches(
            item,
            search=search,
            movement_type=movement_type,
            account_id=account_id,
            category_id=category_id,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
        )
    ]
    filtered.sort(key=lambda item: (_item_date(item), _item_id(item)), reverse=True)

    today = date.today().isoformat()
    income = Decimal("0.00")
    expense = Decimal("0.00")
    for item in filtered:
        if item["kind"] != "transaction":
            continue
        transaction = item["transaction"]
        if transaction.get("neutra") or str(transaction["data"]) > today:
            continue
        if transaction["tipo"] == "entrada":
            income += _money(transaction["valor"])
        elif transaction["tipo"] == "saida":
            expense += _money(transaction["valor"])

    page_items = filtered[offset:offset + limit]
    total = len(filtered)
    return {
        "items": page_items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page_items) < total,
        "summary": {
            "entradas": float(income),
            "saidas": float(expense),
            "saldo": float(income - expense),
        },
    }
