from collections import Counter
from datetime import date
from decimal import Decimal

from repositories.open_finance_reconciliation_repo import (
    buscar_correspondencia,
    confirmar_correspondencia,
    listar_transacoes_bancarias_pendentes,
    listar_transacoes_manuais_para_conciliacao,
    marcar_possiveis_correspondencias,
    rejeitar_correspondencia,
)


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


def detectar_candidatos_conciliacao_service(
    usuario_id: int,
    conexao_id: int | None = None,
) -> int:
    bancarias = listar_transacoes_bancarias_pendentes(usuario_id, conexao_id)
    manuais = listar_transacoes_manuais_para_conciliacao(usuario_id)
    candidatos: dict[int, list[int]] = {}

    for bancaria in bancarias:
        bancaria_id, conta_id, direcao, valor, data_bancaria = bancaria
        correspondentes = [
            int(manual[0])
            for manual in manuais
            if int(manual[1]) == int(conta_id)
            and str(manual[2]) == str(direcao)
            and _money(manual[3]) == _money(valor)
            and abs((_date(manual[4]) - _date(data_bancaria)).days) <= 2
        ]
        if len(correspondentes) == 1:
            candidatos[int(bancaria_id)] = correspondentes

    ocorrencias_manuais = Counter(
        ids[0] for ids in candidatos.values()
    )
    correspondencias = [
        (bancaria_id, ids[0])
        for bancaria_id, ids in candidatos.items()
        if ocorrencias_manuais[ids[0]] == 1
    ]
    return marcar_possiveis_correspondencias(usuario_id, correspondencias)


def _validar_correspondencia_atual(row: tuple) -> None:
    if row[2] is None or row[7] is None:
        raise ReconciliationConflictError(
            "A transacao manual sugerida nao esta mais disponivel."
        )
    if int(row[3]) != int(row[7]):
        raise ReconciliationConflictError(
            "As transacoes nao pertencem mais a mesma conta."
        )
    if str(row[4]) != str(row[8]) or _money(row[5]) != _money(row[9]):
        raise ReconciliationConflictError(
            "Valor ou tipo da transacao manual foi alterado."
        )
    if abs((_date(row[6]) - _date(row[10])).days) > 2:
        raise ReconciliationConflictError(
            "As datas das transacoes nao correspondem mais."
        )


def confirmar_conciliacao_service(
    usuario_id: int,
    transacao_bancaria_id: int,
) -> dict:
    row = buscar_correspondencia(transacao_bancaria_id, usuario_id)
    if row is None:
        raise ReconciliationNotFoundError("Transacao bancaria nao encontrada.")
    if str(row[1]) != "possivel_correspondencia":
        raise ReconciliationConflictError(
            "Esta transacao nao possui uma correspondencia pendente."
        )
    _validar_correspondencia_atual(row)
    if not confirmar_correspondencia(transacao_bancaria_id, usuario_id):
        raise ReconciliationConflictError(
            "A correspondencia foi alterada. Atualize o historico e tente novamente."
        )
    return {
        "transacao_bancaria_id": transacao_bancaria_id,
        "transacao_nivra_id": int(row[2]),
        "status": "conciliada",
    }


def rejeitar_conciliacao_service(
    usuario_id: int,
    transacao_bancaria_id: int,
) -> dict:
    row = buscar_correspondencia(transacao_bancaria_id, usuario_id)
    if row is None:
        raise ReconciliationNotFoundError("Transacao bancaria nao encontrada.")
    if str(row[1]) != "possivel_correspondencia":
        raise ReconciliationConflictError(
            "Esta transacao nao possui uma correspondencia pendente."
        )
    transacao_nivra_id = int(row[2]) if row[2] is not None else None
    if not rejeitar_correspondencia(transacao_bancaria_id, usuario_id):
        raise ReconciliationConflictError(
            "A correspondencia foi alterada. Atualize o historico e tente novamente."
        )
    return {
        "transacao_bancaria_id": transacao_bancaria_id,
        "transacao_nivra_id": transacao_nivra_id,
        "status": "rejeitada",
    }
