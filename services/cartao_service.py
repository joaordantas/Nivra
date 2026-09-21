import calendar
from datetime import date, timedelta

from repositories.cartao_repo import (
    alterar_status_cartao,
    atualizar_cartao,
    atualizar_compra,
    buscar_cartao,
    buscar_compra,
    buscar_fatura,
    buscar_fatura_periodo,
    criar_cartao,
    criar_compra,
    deletar_compra,
    garantir_fatura,
    listar_cartoes,
    listar_compras_fatura,
    listar_faturas,
    pagar_fatura_atomico,
)
from services.categoria_service import obter_categoria
from services.conta_service import obter_conta_ativa
from services.finance_validations import limpar_descricao, validar_data_financeira


def _data_limitada(ano: int, mes: int, dia: int) -> date:
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo_dia))


def _mover_mes(ano: int, mes: int, quantidade: int) -> tuple[int, int]:
    indice = ano * 12 + mes - 1 + quantidade
    return indice // 12, indice % 12 + 1


def calcular_ciclo_fatura(
    data_compra: str | date,
    dia_fechamento: int,
    dia_vencimento: int,
) -> dict:
    compra = date.fromisoformat(data_compra) if isinstance(data_compra, str) else data_compra
    fechamento = _data_limitada(compra.year, compra.month, dia_fechamento)
    if compra > fechamento:
        ano_fechamento, mes_fechamento = _mover_mes(compra.year, compra.month, 1)
        fechamento = _data_limitada(ano_fechamento, mes_fechamento, dia_fechamento)

    deslocamento_vencimento = 1 if dia_vencimento <= dia_fechamento else 0
    ano_vencimento, mes_vencimento = _mover_mes(
        fechamento.year, fechamento.month, deslocamento_vencimento
    )
    vencimento = _data_limitada(ano_vencimento, mes_vencimento, dia_vencimento)
    ano_anterior, mes_anterior = _mover_mes(fechamento.year, fechamento.month, -1)
    inicio = _data_limitada(ano_anterior, mes_anterior, dia_fechamento) + timedelta(days=1)

    return {
        "ano_referencia": vencimento.year,
        "mes_referencia": vencimento.month,
        "data_inicio": inicio.isoformat(),
        "data_fechamento": fechamento.isoformat(),
        "data_vencimento": vencimento.isoformat(),
    }


def calcular_status_fatura(
    data_fechamento: str,
    data_vencimento: str,
    valor_pago: float,
    valor_total: float,
    hoje: date | None = None,
) -> str:
    referencia = hoje or date.today()
    if valor_total > 0 and valor_pago + 0.005 >= valor_total:
        return "paga"
    if referencia > date.fromisoformat(data_vencimento):
        return "vencida"
    if referencia > date.fromisoformat(data_fechamento):
        return "fechada"
    return "aberta"


def _validar_cartao(nome: str, limite_total: float, fechamento: int, vencimento: int) -> str:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("Informe um nome para o cartao.")
    if limite_total <= 0:
        raise ValueError("O limite do cartao deve ser maior que zero.")
    if not 1 <= fechamento <= 31:
        raise ValueError("O dia de fechamento deve estar entre 1 e 31.")
    if not 1 <= vencimento <= 31:
        raise ValueError("O dia de vencimento deve estar entre 1 e 31.")
    return nome_limpo


def _formatar_cartao(cartao: tuple, fatura_atual: dict | None = None) -> dict:
    (
        cartao_id,
        usuario_id,
        nome,
        limite_total,
        fechamento,
        vencimento,
        ativo,
        limite_utilizado,
    ) = cartao
    total = max(float(limite_total), 0.0)
    utilizado = max(float(limite_utilizado), 0.0)
    disponivel = max(total - utilizado, 0.0)
    return {
        "id": cartao_id,
        "usuario_id": usuario_id,
        "nome": nome,
        "limite_total": total,
        "limite_utilizado": utilizado,
        "limite_disponivel": disponivel,
        "percentual_utilizado": round(utilizado * 100 / total, 1) if total > 0 else 0.0,
        "dia_fechamento": fechamento,
        "dia_vencimento": vencimento,
        "ativo": bool(ativo),
        "fatura_atual": fatura_atual,
    }


def _formatar_compra(compra: tuple) -> dict:
    (
        compra_id,
        cartao_id,
        cartao_nome,
        fatura_id,
        valor,
        descricao,
        categoria_id,
        categoria,
        data_compra,
    ) = compra
    return {
        "id": compra_id,
        "cartao_id": cartao_id,
        "cartao": cartao_nome,
        "fatura_id": fatura_id,
        "valor": float(valor),
        "descricao": descricao,
        "categoria_id": categoria_id,
        "categoria": categoria,
        "data": data_compra,
    }


def _formatar_fatura(fatura: tuple, hoje: date | None = None) -> dict:
    (
        fatura_id,
        cartao_id,
        cartao_nome,
        ano_referencia,
        mes_referencia,
        data_inicio,
        data_fechamento,
        data_vencimento,
        valor_total,
        valor_pago,
        data_pagamento,
        conta_pagamento_id,
        conta_pagamento,
        quantidade_compras,
    ) = fatura
    resultado = {
        "id": fatura_id,
        "cartao_id": cartao_id,
        "cartao": cartao_nome,
        "ano_referencia": ano_referencia,
        "mes_referencia": mes_referencia,
        "data_inicio": data_inicio,
        "data_fechamento": data_fechamento,
        "data_vencimento": data_vencimento,
        "valor_total": float(valor_total),
        "valor_pago": float(valor_pago),
        "status": calcular_status_fatura(
            data_fechamento,
            data_vencimento,
            float(valor_pago),
            float(valor_total),
            hoje,
        ),
        "data_pagamento": data_pagamento,
        "conta_pagamento_id": conta_pagamento_id,
        "conta_pagamento": conta_pagamento,
        "quantidade_compras": int(quantidade_compras),
    }
    return resultado


def _garantir_fatura_cartao(cartao: tuple, data_compra: str | date) -> tuple:
    ciclo = calcular_ciclo_fatura(data_compra, int(cartao[4]), int(cartao[5]))
    fatura_id = garantir_fatura(
        int(cartao[0]),
        int(cartao[1]),
        ciclo["ano_referencia"],
        ciclo["mes_referencia"],
        ciclo["data_inicio"],
        ciclo["data_fechamento"],
        ciclo["data_vencimento"],
    )
    fatura = buscar_fatura(fatura_id, int(cartao[1]))
    if fatura is None:
        raise ValueError("Nao foi possivel criar a fatura.")
    return fatura


def criar_cartao_service(
    usuario_id: int, nome: str, limite_total: float, fechamento: int, vencimento: int
) -> dict:
    nome_limpo = _validar_cartao(nome, limite_total, fechamento, vencimento)
    cartao_id = criar_cartao(usuario_id, nome_limpo, limite_total, fechamento, vencimento)
    cartao = buscar_cartao(cartao_id, usuario_id)
    if cartao is None:
        raise ValueError("Cartao nao encontrado.")
    return _formatar_cartao(cartao, _formatar_fatura(_garantir_fatura_cartao(cartao, date.today())))


def listar_cartoes_formatados(
    usuario_id: int,
    incluir_inativos: bool = True,
    *,
    hoje: date | None = None,
) -> list[dict]:
    resultado = []
    referencia = hoje or date.today()
    for cartao in listar_cartoes(usuario_id, incluir_inativos):
        fatura = _garantir_fatura_cartao(cartao, referencia)
        resultado.append(_formatar_cartao(cartao, _formatar_fatura(fatura, referencia)))
    return resultado


def atualizar_cartao_service(
    cartao_id: int,
    usuario_id: int,
    nome: str,
    limite_total: float,
    fechamento: int,
    vencimento: int,
) -> dict:
    nome_limpo = _validar_cartao(nome, limite_total, fechamento, vencimento)
    atual = buscar_cartao(cartao_id, usuario_id)
    if atual is None:
        raise ValueError("Cartao nao encontrado.")
    if limite_total + 0.005 < float(atual[7]):
        raise ValueError("O novo limite nao pode ser menor que o valor utilizado.")
    atualizar_cartao(cartao_id, usuario_id, nome_limpo, limite_total, fechamento, vencimento)
    cartao = buscar_cartao(cartao_id, usuario_id)
    if cartao is None:
        raise ValueError("Cartao nao encontrado.")
    return _formatar_cartao(cartao, _formatar_fatura(_garantir_fatura_cartao(cartao, date.today())))


def alterar_status_cartao_service(cartao_id: int, usuario_id: int, ativo: bool) -> dict:
    if buscar_cartao(cartao_id, usuario_id) is None:
        raise ValueError("Cartao nao encontrado.")
    alterar_status_cartao(cartao_id, usuario_id, ativo)
    cartao = buscar_cartao(cartao_id, usuario_id)
    if cartao is None:
        raise ValueError("Cartao nao encontrado.")
    return _formatar_cartao(cartao, _formatar_fatura(_garantir_fatura_cartao(cartao, date.today())))


def obter_fatura_atual_service(cartao_id: int, usuario_id: int) -> dict:
    cartao = buscar_cartao(cartao_id, usuario_id)
    if cartao is None:
        raise ValueError("Cartao nao encontrado.")
    return _formatar_fatura(_garantir_fatura_cartao(cartao, date.today()))


def listar_faturas_service(
    cartao_id: int,
    usuario_id: int,
    *,
    hoje: date | None = None,
) -> list[dict]:
    cartao = buscar_cartao(cartao_id, usuario_id)
    if cartao is None:
        raise ValueError("Cartao nao encontrado.")
    referencia = hoje or date.today()
    _garantir_fatura_cartao(cartao, referencia)
    return [
        _formatar_fatura(fatura, referencia)
        for fatura in listar_faturas(cartao_id, usuario_id)
    ]


def obter_fatura_service(fatura_id: int, usuario_id: int) -> dict:
    fatura = buscar_fatura(fatura_id, usuario_id)
    if fatura is None:
        raise ValueError("Fatura nao encontrada.")
    resultado = _formatar_fatura(fatura)
    resultado["compras"] = [
        _formatar_compra(compra) for compra in listar_compras_fatura(fatura_id, usuario_id)
    ]
    return resultado


def _validar_compra(
    cartao_id: int,
    usuario_id: int,
    valor: float,
    descricao: str | None,
    categoria_id: int,
    data_compra: str,
) -> tuple[tuple, str]:
    if valor <= 0:
        raise ValueError("O valor da compra deve ser maior que zero.")
    validar_data_financeira(data_compra)
    descricao_limpa = limpar_descricao(descricao)
    if not descricao_limpa:
        raise ValueError("Informe uma descricao para a compra.")
    cartao = buscar_cartao(cartao_id, usuario_id, True)
    if cartao is None:
        raise ValueError("Cartao ativo nao encontrado.")
    if obter_categoria(categoria_id, usuario_id) is None:
        raise ValueError("Categoria nao encontrada.")
    return cartao, descricao_limpa


def criar_compra_service(
    cartao_id: int,
    usuario_id: int,
    valor: float,
    descricao: str | None,
    categoria_id: int,
    data_compra: str,
) -> dict:
    cartao, descricao_limpa = _validar_compra(
        cartao_id, usuario_id, valor, descricao, categoria_id, data_compra
    )
    if float(cartao[7]) + valor > float(cartao[3]) + 0.005:
        raise ValueError("Limite insuficiente para esta compra.")
    fatura = _garantir_fatura_cartao(cartao, data_compra)
    if float(fatura[9]) > 0:
        raise ValueError("Nao e possivel adicionar uma compra a uma fatura paga.")
    compra_id = criar_compra(
        cartao_id, int(fatura[0]), usuario_id, valor, descricao_limpa, categoria_id, data_compra
    )
    compra = buscar_compra(compra_id, usuario_id)
    if compra is None:
        raise ValueError("Compra nao encontrada.")
    return _formatar_compra(compra)


def atualizar_compra_service(
    compra_id: int,
    cartao_id: int,
    usuario_id: int,
    valor: float,
    descricao: str | None,
    categoria_id: int,
    data_compra: str,
) -> dict:
    compra_atual = buscar_compra(compra_id, usuario_id)
    if compra_atual is None:
        raise ValueError("Compra nao encontrada.")
    fatura_atual = buscar_fatura(int(compra_atual[3]), usuario_id)
    if fatura_atual is None or float(fatura_atual[9]) > 0:
        raise ValueError("Compras de uma fatura paga nao podem ser alteradas.")
    cartao, descricao_limpa = _validar_compra(
        cartao_id, usuario_id, valor, descricao, categoria_id, data_compra
    )
    utilizado_ajustado = float(cartao[7])
    if int(compra_atual[1]) == cartao_id:
        utilizado_ajustado -= float(compra_atual[4])
    if utilizado_ajustado + valor > float(cartao[3]) + 0.005:
        raise ValueError("Limite insuficiente para esta compra.")
    nova_fatura = _garantir_fatura_cartao(cartao, data_compra)
    if float(nova_fatura[9]) > 0:
        raise ValueError("Nao e possivel mover a compra para uma fatura paga.")
    atualizar_compra(
        compra_id,
        usuario_id,
        cartao_id,
        int(nova_fatura[0]),
        valor,
        descricao_limpa,
        categoria_id,
        data_compra,
    )
    atualizada = buscar_compra(compra_id, usuario_id)
    if atualizada is None:
        raise ValueError("Compra nao encontrada.")
    return _formatar_compra(atualizada)


def deletar_compra_service(compra_id: int, usuario_id: int) -> bool:
    compra = buscar_compra(compra_id, usuario_id)
    if compra is None:
        return False
    fatura = buscar_fatura(int(compra[3]), usuario_id)
    if fatura is None or float(fatura[9]) > 0:
        raise ValueError("Compras de uma fatura paga nao podem ser excluidas.")
    return deletar_compra(compra_id, usuario_id)


def pagar_fatura_service(
    fatura_id: int, conta_id: int, usuario_id: int, data_pagamento: str
) -> dict:
    validar_data_financeira(data_pagamento)
    fatura = buscar_fatura(fatura_id, usuario_id)
    if fatura is None:
        raise ValueError("Fatura nao encontrada.")
    valor_total = float(fatura[8])
    valor_pago = float(fatura[9])
    if valor_pago > 0:
        raise ValueError("Esta fatura ja foi paga.")
    if valor_total <= 0:
        raise ValueError("Esta fatura nao possui compras para pagar.")
    if obter_conta_ativa(conta_id, usuario_id) is None:
        raise ValueError("Conta de pagamento nao encontrada.")
    if not pagar_fatura_atomico(fatura_id, conta_id, usuario_id, valor_total, data_pagamento):
        raise ValueError("Esta fatura ja foi paga ou os dados de pagamento sao invalidos.")
    return obter_fatura_service(fatura_id, usuario_id)
