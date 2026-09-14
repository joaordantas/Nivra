from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from repositories.parcelamento_repo import (
    atualizar_parcelamento_atomico,
    buscar_parcelamento,
    criar_parcelamento_atomico,
    excluir_parcelamento_atomico,
    listar_parcelamentos,
    listar_parcelas,
)
from services.finance_validations import limpar_descricao
from services.open_finance_reconciliation_service import (
    detectar_candidatos_conciliacao_service,
)
from services.transacao_service import validar_dados_transacao


CENTAVO = Decimal("0.01")


def dividir_valor_em_parcelas(
    valor_total: Decimal | float | str, quantidade_parcelas: int
) -> list[Decimal]:
    if quantidade_parcelas < 2:
        raise ValueError("O parcelamento deve possuir pelo menos duas parcelas.")
    total = Decimal(str(valor_total)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if total <= 0:
        raise ValueError("O valor total deve ser maior que zero.")
    total_centavos = int(total * 100)
    if total_centavos < quantidade_parcelas:
        raise ValueError("O valor total deve permitir ao menos um centavo por parcela.")
    base, restante = divmod(total_centavos, quantidade_parcelas)
    return [
        Decimal(base + (1 if indice < restante else 0)) / 100
        for indice in range(quantidade_parcelas)
    ]


def calcular_data_parcela(data_inicial: date, deslocamento_meses: int) -> date:
    indice_mes = data_inicial.month - 1 + deslocamento_meses
    ano = data_inicial.year + indice_mes // 12
    mes = indice_mes % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(data_inicial.day, ultimo_dia))


def _formatar_parcela(parcela: tuple, quantidade_parcelas: int) -> dict:
    (
        transacao_id,
        numero_parcela,
        valor,
        data_parcela,
        tipo,
        categoria_id,
        categoria,
        conta_id,
        conta,
        comentario,
    ) = parcela
    data_iso = str(data_parcela)
    return {
        "id": int(transacao_id),
        "numero_parcela": int(numero_parcela),
        "quantidade_parcelas": quantidade_parcelas,
        "valor": float(valor),
        "data": data_iso,
        "tipo": str(tipo),
        "categoria_id": int(categoria_id) if categoria_id is not None else None,
        "categoria": str(categoria),
        "conta_id": int(conta_id) if conta_id is not None else None,
        "conta": str(conta),
        "comentario": comentario,
        "status_temporal": (
            "data_atingida" if data_iso <= date.today().isoformat() else "futura"
        ),
    }


def _formatar_resumo_plano(plano: tuple) -> dict:
    (
        parcelamento_id,
        descricao,
        valor_total,
        quantidade_parcelas,
        data_inicial,
        criado_em,
        atualizado_em,
        parcelas_persistidas,
        valor_persistido,
        primeira_parcela_data,
        ultima_parcela_data,
        parcelas_com_data_atingida,
        proxima_parcela_data,
    ) = plano
    return {
        "id": int(parcelamento_id),
        "descricao": str(descricao),
        "valor_total": float(valor_total),
        "quantidade_parcelas": int(quantidade_parcelas),
        "data_inicial": str(data_inicial),
        "criado_em": criado_em,
        "atualizado_em": atualizado_em,
        "parcelas_persistidas": int(parcelas_persistidas),
        "valor_persistido": float(valor_persistido),
        "primeira_parcela_data": str(primeira_parcela_data),
        "ultima_parcela_data": str(ultima_parcela_data),
        "parcelas_com_data_atingida": int(parcelas_com_data_atingida),
        "parcelas_futuras": int(quantidade_parcelas) - int(parcelas_com_data_atingida),
        "proxima_parcela_data": (
            str(proxima_parcela_data) if proxima_parcela_data is not None else None
        ),
    }


def _formatar_plano_do_usuario(
    plano: tuple, usuario_id: int, *, detalhado: bool
) -> dict:
    resultado = _formatar_resumo_plano(plano)
    if detalhado:
        resultado["parcelas"] = [
            _formatar_parcela(parcela, resultado["quantidade_parcelas"])
            for parcela in listar_parcelas(resultado["id"], usuario_id)
        ]
    return resultado


def criar_parcelamento_service(
    usuario_id: int,
    descricao: str | None,
    valor_total: Decimal | float | str,
    quantidade_parcelas: int,
    data_inicial: date,
    tipo: str,
    categoria_id: int | None = None,
    conta_id: int | None = None,
) -> dict:
    descricao_limpa = limpar_descricao(descricao)
    if not descricao_limpa:
        raise ValueError("Informe uma descricao para o parcelamento.")
    valores = dividir_valor_em_parcelas(valor_total, quantidade_parcelas)
    total = sum(valores, Decimal("0.00"))
    validar_dados_transacao(
        total,
        tipo,
        categoria_id,
        data_inicial.isoformat(),
        usuario_id,
        conta_id,
    )
    parcelas = [
        (numero, valor, calcular_data_parcela(data_inicial, numero - 1))
        for numero, valor in enumerate(valores, start=1)
    ]
    parcelamento_id = criar_parcelamento_atomico(
        usuario_id,
        descricao_limpa,
        total,
        quantidade_parcelas,
        data_inicial,
        tipo,
        categoria_id,
        conta_id,
        parcelas,
    )
    detectar_candidatos_conciliacao_service(usuario_id)
    return obter_parcelamento_service(parcelamento_id, usuario_id)


def obter_parcelamento_service(parcelamento_id: int, usuario_id: int) -> dict:
    plano = buscar_parcelamento(parcelamento_id, usuario_id)
    if plano is None:
        raise ValueError("Parcelamento nao encontrado.")
    return _formatar_plano_do_usuario(plano, usuario_id, detalhado=True)


def listar_parcelamentos_service(usuario_id: int) -> list[dict]:
    return [
        _formatar_plano_do_usuario(plano, usuario_id, detalhado=False)
        for plano in listar_parcelamentos(usuario_id)
    ]


def atualizar_parcelamento_service(
    parcelamento_id: int,
    usuario_id: int,
    descricao: str | None,
    categoria_id: int | None,
    conta_id: int | None,
) -> dict | None:
    plano = buscar_parcelamento(parcelamento_id, usuario_id)
    if plano is None:
        return None
    descricao_limpa = limpar_descricao(descricao)
    if not descricao_limpa:
        raise ValueError("Informe uma descricao para o parcelamento.")
    parcelas = listar_parcelas(parcelamento_id, usuario_id)
    if not parcelas:
        raise ValueError("O parcelamento nao possui parcelas validas.")
    primeira_parcela = parcelas[0]
    validar_dados_transacao(
        Decimal("0.01"),
        str(primeira_parcela[4]),
        categoria_id,
        str(primeira_parcela[3]),
        usuario_id,
        conta_id,
    )
    if not atualizar_parcelamento_atomico(
        parcelamento_id,
        usuario_id,
        descricao_limpa,
        categoria_id,
        conta_id,
    ):
        return None
    detectar_candidatos_conciliacao_service(usuario_id)
    return obter_parcelamento_service(parcelamento_id, usuario_id)


def excluir_parcelamento_service(parcelamento_id: int, usuario_id: int) -> bool:
    excluido = excluir_parcelamento_atomico(parcelamento_id, usuario_id)
    if excluido:
        detectar_candidatos_conciliacao_service(usuario_id)
    return excluido
