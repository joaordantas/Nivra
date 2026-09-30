from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from services.categoria_service import listar_categorias_formatadas
from services.conta_service import listar_contas_formatadas
from services.transacao_service import localizar_transacoes_lumi_service
from services.lumi_action_confirmation_service import (
    ActionConfirmation,
    ActionType,
    criar_confirmacao_pendente,
)


MAX_ACTION_AMOUNT = Decimal("1000000000.00")
ACTION_INTENT_PATTERN = re.compile(
    r"^(?:crie|criar|registre|registrar|adicione|adicionar|lance|lancar|gastei|recebi|mude|mudar|corrija|corrigir|troque|trocar|altere|alterar|edite|editar)\b",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(r"(?:r\$\s*)?(-?[\d.]+(?:,[\d]{1,2})?)\b", re.IGNORECASE)
LABEL_PATTERN = re.compile(r"\b(conta|categoria|descri(?:ç|c)ão|descricao|data)\s*:\s*([^|,;]+)", re.IGNORECASE)
SIMPLE_EXPENSE_PATTERN = re.compile(
    r"^gastei\s+(?:r\$\s*)?[\d.,]+\s+em\s+(?P<description>.+?)\s+pela\s+"
    r"(?P<account>.+?)\s+na\s+categoria\s+(?P<category>.+?)\s+hoje\.?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ActionProposalDecision:
    action_type: ActionType
    summary: str
    payload: dict[str, object]
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    confirmation: ActionConfirmation | None


def _normalize(value: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.split())


def reconhecer_intencao_acao(message: str) -> ActionType | None:
    normalized = _normalize(message)
    if not ACTION_INTENT_PATTERN.match(normalized):
        return None
    if any(word in normalized for word in ("despesa", "gasto", "gastei")):
        return "create_expense"
    if any(word in normalized for word in ("receita", "renda", "recebi")):
        return "create_income"
    if any(word in normalized for word in ("mude", "mudar", "corrija", "corrigir", "troque", "trocar", "altere", "alterar", "edite", "editar")):
        return "update_transaction"
    return None


def _edit_change_fields(message: str, usuario_id: int) -> dict[str, object]:
    normalized = _normalize(message)
    changes: dict[str, object] = {}
    labeled = _parse_labeled_fields(message)
    if labeled.get("description"):
        changes["description"] = labeled["description"]
    if labeled.get("data"):
        changes["date"] = labeled["data"]
    amount_match = re.search(r"(?:valor|para)\s+(?:r\$\s*)?([\d.]+(?:,[\d]{1,2})?)", message, re.I)
    if amount_match:
        amount = _parse_amount(amount_match.group(1))
        if amount is not None:
            changes["amount"] = format(amount, "f")
    accounts = [item for item in listar_contas_formatadas(usuario_id) if bool(item["ativo"])]
    categories = listar_categorias_formatadas(usuario_id)
    for item in categories:
        if _normalize(str(item["nome"])) in normalized and "categor" in normalized:
            changes["category"] = {"id": int(item["id"]), "name": str(item["nome"])}
    for item in accounts:
        if _normalize(str(item["nome"])) in normalized and "conta" in normalized:
            changes["account"] = {"id": int(item["id"]), "name": str(item["nome"])}
    return changes


def criar_proposta_de_edicao(
    usuario_id: int,
    transacao_id: int,
    changes: dict[str, object],
) -> ActionProposalDecision:
    from services.transacao_service import localizar_transacoes_lumi_service
    candidates = [item for item in localizar_transacoes_lumi_service(usuario_id) if int(item["id"]) == transacao_id]
    if len(candidates) != 1:
        return ActionProposalDecision("update_transaction", "Não encontrei uma transação manual editável.", {}, (), ("A transação não pode ser editada pela Lumi.",), None)
    current = candidates[0]
    allowed = {"description", "amount", "date", "category", "account"}
    if not changes or set(changes) - allowed:
        return ActionProposalDecision("update_transaction", "Informe uma alteração permitida.", current, ("alteração",), (), None)
    after = {
        "amount": str(changes.get("amount", f"{current['valor']:.2f}")),
        "description": changes.get("description", current["comentario"]),
        "date": changes.get("date", str(current["data"])),
        "account": changes.get("account", {"id": current["conta_id"], "name": current["conta"]}),
        "category": changes.get("category", {"id": current["categoria_id"], "name": current["categoria"]}),
    }
    payload = {"transaction_id": transacao_id, "before": current, "after": after, "changes": sorted(changes)}
    confirmation = criar_confirmacao_pendente(usuario_id, "update_transaction", payload)
    return ActionProposalDecision(
        "update_transaction", "Proposta para editar a transação selecionada.", payload, (), (), confirmation,
    )


def _parse_amount(message: str) -> Decimal | None:
    match = AMOUNT_PATTERN.search(message)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return amount


def _parse_labeled_fields(message: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for label, value in LABEL_PATTERN.findall(message):
        normalized_label = _normalize(label)
        key = "description" if normalized_label in {"descricao"} else normalized_label
        parsed[key] = value.strip()
    return parsed


def _find_owned_entity(items: list[dict], name: str | None) -> dict | None:
    if not name:
        return None
    normalized = _normalize(name)
    return next((item for item in items if _normalize(str(item["nome"])) == normalized), None)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _describe(action_type: ActionType, amount: Decimal | None, description: str | None) -> str:
    action = "despesa" if action_type == "create_expense" else "receita"
    if amount is None:
        return f"Proposta de {action}; informe os dados faltantes para revisão."
    subject = f" para {description}" if description else ""
    return f"Proposta de {action} de R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + subject + "."


def criar_proposta_da_mensagem(
    message: str,
    usuario_id: int,
    *,
    today: date | None = None,
) -> ActionProposalDecision | None:
    action_type = reconhecer_intencao_acao(message)
    if action_type is None:
        return None
    if action_type == "update_transaction":
        normalized = _normalize(message)
        target = re.search(r"(?:compra|despesa|transacao)\s+(?:de\s+)?([a-z0-9 ]+?)(?:\s+(?:de ontem|de hoje|do dia|para|na categoria|pela conta)|$)", normalized)
        description = target.group(1).strip() if target else None
        candidates = localizar_transacoes_lumi_service(usuario_id, descricao=description)
        if len(candidates) != 1:
            options = ", ".join(f"{item['comentario']} — R$ {item['valor']:.2f} — {item['data']}" for item in candidates[:5])
            message_text = "Não encontrei uma única transação para editar."
            if len(candidates) > 1:
                message_text += f" Escolha uma: {options}."
            return ActionProposalDecision("update_transaction", message_text, {}, ("transação inequívoca",), (), None)
        return criar_proposta_de_edicao(usuario_id, int(candidates[0]["id"]), _edit_change_fields(message, usuario_id))
    fields = _parse_labeled_fields(message)
    simple_expense = SIMPLE_EXPENSE_PATTERN.fullmatch(message.strip()) if action_type == "create_expense" else None
    if simple_expense and not fields:
        fields = {
            "description": simple_expense.group("description").strip(),
            "conta": simple_expense.group("account").strip(),
            "categoria": simple_expense.group("category").strip(),
            "data": (today or date.today()).isoformat(),
        }
    amount = _parse_amount(message)
    warnings: list[str] = []
    if amount is not None and (not amount.is_finite() or amount <= 0 or amount > MAX_ACTION_AMOUNT):
        warnings.append("O valor informado não é válido para uma proposta financeira.")
        amount = None

    accounts = [item for item in listar_contas_formatadas(usuario_id) if bool(item["ativo"])]
    categories = listar_categorias_formatadas(usuario_id)
    account = _find_owned_entity(accounts, fields.get("conta"))
    category = _find_owned_entity(categories, fields.get("categoria"))
    if fields.get("conta") and account is None:
        warnings.append("A conta informada não foi encontrada entre suas contas ativas.")
    if fields.get("categoria") and category is None:
        warnings.append("A categoria informada não foi encontrada nas suas categorias.")
    provided_date = fields.get("data")
    parsed_date = _parse_date(provided_date)
    if provided_date and parsed_date is None:
        warnings.append("A data deve usar o formato AAAA-MM-DD.")

    description = fields.get("description")
    if description and len(description) > 255:
        warnings.append("A descrição excede o limite permitido.")
        description = None
    payload: dict[str, object] = {
        "amount": format(amount, "f") if amount is not None else None,
        "description": description or None,
        "date": parsed_date.isoformat() if parsed_date else None,
        "account": {"id": int(account["id"]), "name": str(account["nome"])} if account else None,
        "category": {"id": int(category["id"]), "name": str(category["nome"])} if category else None,
    }
    missing: list[str] = []
    if amount is None:
        missing.append("valor")
    if not description:
        missing.append("descrição")
    if account is None:
        missing.append("conta")
    if category is None:
        missing.append("categoria")
    if parsed_date is None:
        missing.append("data")
    confirmation = None
    if not missing and not warnings:
        confirmation = criar_confirmacao_pendente(usuario_id, action_type, payload)
    return ActionProposalDecision(
        action_type,
        _describe(action_type, amount, description),
        payload,
        tuple(missing),
        tuple(warnings),
        confirmation,
    )
