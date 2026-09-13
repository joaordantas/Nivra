from repositories.dashboard_repo import (
    a_receber_por_cliente,
    total_a_receber,
)
from services.transacao_service import obter_resumo_financeiro


def obter_lucro_por_periodo(data_inicio: str, data_fim: str, usuario_id: int) -> dict:
    resumo = obter_resumo_financeiro(usuario_id, data_inicio, data_fim)
    return {
        "entrada": resumo["entradas"],
        "saida": resumo["saidas"],
        "lucro": resumo["saldo"],
    }


def obter_total_a_receber(usuario_id: int) -> float:
    return float(total_a_receber(usuario_id))


def obter_a_receber_por_cliente(usuario_id: int) -> list[dict]:
    dados = a_receber_por_cliente(usuario_id)
    return [
        {"cliente": cliente, "valor_pendente": float(valor)}
        for cliente, valor in dados
    ]
