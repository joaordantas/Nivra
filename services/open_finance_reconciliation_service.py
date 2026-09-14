import json
import re
import unicodedata
from collections import Counter
from datetime import date
from decimal import Decimal

from repositories.open_finance_reconciliation_repo import (
    buscar_candidato,
    confirmar_correspondencia,
    listar_ids_candidatos,
    listar_sugestoes_conciliacao,
    listar_transacoes_bancarias_para_conciliacao,
    listar_transacoes_manuais_para_conciliacao,
    marcar_bancos_ambiguos,
    rejeitar_correspondencia,
    salvar_sugestoes_conciliacao,
)
from utils.categorias_padrao import is_provider_neutral_movement


DATE_WINDOW_DAYS = 2
IGNORED_DESCRIPTION_TOKENS = {
    "compra", "pagamento", "debito", "credito", "pix", "ted", "doc",
    "cartao", "estabelecimento", "lancamento",
}


class ReconciliationNotFoundError(RuntimeError):
    pass


class ReconciliationConflictError(RuntimeError):
    pass


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _metadata(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def normalizar_descricao(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    tokens = [
        token for token in re.findall(r"[a-z]+", text)
        if token not in IGNORED_DESCRIPTION_TOKENS and len(token) > 1
    ]
    return " ".join(tokens)


def _description_points(bank_description: object, manual_description: object) -> tuple[int, str | None]:
    bank = normalizar_descricao(bank_description)
    manual = normalizar_descricao(manual_description)
    if not bank or not manual:
        return 0, None
    if bank == manual:
        return 10, "descricao_semelhante"
    bank_tokens, manual_tokens = set(bank.split()), set(manual.split())
    overlap = len(bank_tokens & manual_tokens) / max(len(bank_tokens | manual_tokens), 1)
    if overlap >= 0.5:
        return 5, "descricao_semelhante"
    return 0, None


def _score_candidate(bank: tuple, manual: tuple) -> dict | None:
    _, account_id, direction, amount, bank_date, description, _ = bank
    manual_id, manual_account, manual_direction, manual_amount, manual_date, manual_description = manual
    if int(manual_account) != int(account_id):
        return None
    if str(manual_direction) != str(direction) or _money(manual_amount) != _money(amount):
        return None
    date_distance = abs((_date(manual_date) - _date(bank_date)).days)
    if date_distance > DATE_WINDOW_DAYS:
        return None

    reasons = ["mesma_conta", "mesmo_valor", "mesma_direcao"]
    date_points = 15 if date_distance == 0 else 10 if date_distance == 1 else 5
    reasons.append("mesmo_dia" if date_distance == 0 else "data_proxima")
    description_points, description_reason = _description_points(description, manual_description)
    if description_reason:
        reasons.append(description_reason)
    score = 75 + date_points + description_points
    confidence = "alta" if score >= 90 else "media" if score >= 85 else "baixa"
    return {
        "transacao_nivra_id": int(manual_id),
        "confianca": confidence,
        "score": min(score, 100),
        "motivos": reasons,
    }


def _is_neutral_bank_transaction(bank: tuple) -> bool:
    metadata = _metadata(bank[6])
    return is_provider_neutral_movement(
        "pluggy", metadata.get("category_id"), metadata.get("category_name")
    )


def detectar_candidatos_conciliacao_service(usuario_id: int, conexao_id: int | None = None) -> int:
    banks = listar_transacoes_bancarias_para_conciliacao(usuario_id, conexao_id)
    manuals = listar_transacoes_manuais_para_conciliacao(usuario_id)
    suggestions_by_bank: dict[int, list[dict]] = {}
    manual_occurrences: Counter[int] = Counter()

    for bank in banks:
        suggestions = [] if _is_neutral_bank_transaction(bank) else [
            candidate for manual in manuals
            if (candidate := _score_candidate(bank, manual)) is not None
        ]
        bank_id = int(bank[0])
        suggestions_by_bank[bank_id] = suggestions
        manual_occurrences.update(item["transacao_nivra_id"] for item in suggestions)

    marked = 0
    for bank_id, suggestions in suggestions_by_bank.items():
        marked += salvar_sugestoes_conciliacao(usuario_id, bank_id, suggestions)
    ambiguous_banks = [
        bank_id for bank_id, suggestions in suggestions_by_bank.items()
        if len(suggestions) > 1 or any(manual_occurrences[item["transacao_nivra_id"]] > 1 for item in suggestions)
    ]
    marcar_bancos_ambiguos(usuario_id, ambiguous_banks)
    return marked


def _validar_correspondencia_atual(row: tuple) -> None:
    if row[2] is None:
        raise ReconciliationConflictError("A transação manual sugerida não está mais disponível.")
    if int(row[3]) != int(row[7]):
        raise ReconciliationConflictError("As transações não pertencem mais à mesma conta.")
    if str(row[4]) != str(row[8]) or _money(row[5]) != _money(row[9]):
        raise ReconciliationConflictError("Valor ou tipo da transação manual foi alterado.")
    if abs((_date(row[6]) - _date(row[10])).days) > DATE_WINDOW_DAYS:
        raise ReconciliationConflictError("As datas das transações não correspondem mais.")


def _resolve_manual_id(usuario_id: int, bank_id: int, manual_id: int | None) -> int:
    if manual_id is not None:
        return manual_id
    candidates = listar_ids_candidatos(bank_id, usuario_id)
    if not candidates:
        raise ReconciliationNotFoundError("Possível correspondência não encontrada.")
    if len(candidates) > 1:
        raise ReconciliationConflictError("Encontramos mais de uma possível correspondência. Escolha a correta.")
    return candidates[0]


def confirmar_conciliacao_service(usuario_id: int, transacao_bancaria_id: int, transacao_nivra_id: int | None = None) -> dict:
    manual_id = _resolve_manual_id(usuario_id, transacao_bancaria_id, transacao_nivra_id)
    row = buscar_candidato(transacao_bancaria_id, manual_id, usuario_id)
    if row is None:
        raise ReconciliationNotFoundError("Possível correspondência não encontrada.")
    _validar_correspondencia_atual(row)
    if not confirmar_correspondencia(transacao_bancaria_id, manual_id, usuario_id):
        raise ReconciliationConflictError("A correspondência já foi alterada. Atualize e tente novamente.")
    return {"transacao_bancaria_id": transacao_bancaria_id, "transacao_nivra_id": manual_id, "status": "conciliada"}


def rejeitar_conciliacao_service(usuario_id: int, transacao_bancaria_id: int, transacao_nivra_id: int | None = None) -> dict:
    manual_id = _resolve_manual_id(usuario_id, transacao_bancaria_id, transacao_nivra_id)
    if not rejeitar_correspondencia(transacao_bancaria_id, manual_id, usuario_id):
        raise ReconciliationConflictError("A correspondência já foi alterada. Atualize e tente novamente.")
    return {"transacao_bancaria_id": transacao_bancaria_id, "transacao_nivra_id": manual_id, "status": "rejeitada"}


def listar_sugestoes_conciliacao_service(usuario_id: int) -> list[dict]:
    grouped: dict[int, dict] = {}
    for row in listar_sugestoes_conciliacao(usuario_id):
        bank_id = int(row[0])
        item = grouped.setdefault(bank_id, {
            "transacao_bancaria_id": bank_id,
            "descricao": str(row[1]), "valor": float(row[2]), "data": str(row[3]),
            "direcao": str(row[4]), "conta_id": int(row[5]), "conta": str(row[6]),
            "instituicao_nome": str(row[7]), "ambigua": str(row[8]) == "ambigua",
            "candidatos": [],
        })
        try:
            reasons = json.loads(str(row[16]))
        except json.JSONDecodeError:
            reasons = []
        item["candidatos"].append({
            "transacao_nivra_id": int(row[9]), "descricao": str(row[10] or "Movimentação manual"),
            "valor": float(row[11]), "data": str(row[12]), "direcao": str(row[13]),
            "confianca": str(row[14]), "motivos": reasons,
        })
    return list(grouped.values())


def confirmar_lote_alta_confianca_service(usuario_id: int) -> dict:
    suggestions = listar_sugestoes_conciliacao_service(usuario_id)
    safe = [item for item in suggestions if not item["ambigua"] and len(item["candidatos"]) == 1 and item["candidatos"][0]["confianca"] == "alta"]
    confirmed = 0
    for item in safe:
        try:
            confirmar_conciliacao_service(usuario_id, item["transacao_bancaria_id"], item["candidatos"][0]["transacao_nivra_id"])
            confirmed += 1
        except (ReconciliationConflictError, ReconciliationNotFoundError):
            continue
    return {"confirmadas": confirmed, "solicitadas": len(safe)}
