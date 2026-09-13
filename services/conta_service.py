from repositories.conta_repo import (
    alterar_status_conta,
    atualizar_conta,
    buscar_conta_por_id,
    criar_conta,
    definir_conta_principal,
    listar_contas_com_saldo,
    obter_uso_contas,
)


TIPOS_DE_CONTA = {"corrente", "poupanca", "digital", "dinheiro", "outro"}


def _validar_dados_conta(nome: str, tipo: str) -> str:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("Informe um nome para a conta.")
    if tipo not in TIPOS_DE_CONTA:
        raise ValueError("Tipo de conta invalido.")
    return nome_limpo


def _formatar_conta(conta: tuple) -> dict:
    (
        conta_id,
        nome,
        tipo,
        saldo_inicial,
        ativo,
        principal,
        saldo_atual,
        conta_externa_id,
        instituicao_nome,
        ultima_sincronizacao_em,
    ) = conta
    return {
        "id": conta_id,
        "nome": nome,
        "tipo": tipo,
        "saldo_inicial": float(saldo_inicial),
        "saldo_atual": float(saldo_atual),
        "ativo": bool(ativo),
        "principal": bool(principal),
        "percentual_uso": 0.0,
        "mais_utilizada": False,
        "origem": "open_finance" if conta_externa_id is not None else "manual",
        "conta_externa_id": int(conta_externa_id) if conta_externa_id is not None else None,
        "instituicao_nome": str(instituicao_nome) if instituicao_nome is not None else None,
        "ultima_sincronizacao_em": (
            str(ultima_sincronizacao_em) if ultima_sincronizacao_em is not None else None
        ),
    }


def criar_conta_service(nome: str, tipo: str, saldo_inicial: float, usuario_id: int) -> dict:
    nome_limpo = _validar_dados_conta(nome, tipo)
    conta_id = criar_conta(nome_limpo, tipo, saldo_inicial, usuario_id)
    return {
        "id": conta_id,
        "nome": nome_limpo,
        "tipo": tipo,
        "saldo_inicial": float(saldo_inicial),
        "saldo_atual": float(saldo_inicial),
        "ativo": True,
        "principal": False,
        "percentual_uso": 0.0,
        "mais_utilizada": False,
        "origem": "manual",
        "conta_externa_id": None,
        "instituicao_nome": None,
        "ultima_sincronizacao_em": None,
    }


def listar_contas_formatadas(usuario_id: int, incluir_inativas: bool = False) -> list[dict]:
    contas = [
        _formatar_conta(conta)
        for conta in listar_contas_com_saldo(usuario_id, incluir_inativas)
    ]
    usos = obter_uso_contas(usuario_id)
    total_usos = sum(usos.values())
    maior_uso = max(usos.values(), default=0)
    for conta in contas:
        quantidade = usos.get(conta["id"], 0)
        conta["percentual_uso"] = round(quantidade * 100 / total_usos, 1) if total_usos else 0.0
        conta["mais_utilizada"] = maior_uso > 0 and quantidade == maior_uso
    return contas


def obter_conta(conta_id: int, usuario_id: int, somente_ativa: bool = True) -> tuple | None:
    return buscar_conta_por_id(conta_id, usuario_id, somente_ativa)


def obter_conta_ativa(conta_id: int, usuario_id: int) -> tuple | None:
    return obter_conta(conta_id, usuario_id, True)


def atualizar_conta_service(
    conta_id: int,
    nome: str,
    tipo: str,
    saldo_inicial: float,
    usuario_id: int,
) -> dict:
    nome_limpo = _validar_dados_conta(nome, tipo)
    if obter_conta(conta_id, usuario_id, False) is None:
        raise ValueError("Conta nao encontrada.")
    atualizar_conta(conta_id, nome_limpo, tipo, saldo_inicial, usuario_id)
    conta = obter_conta(conta_id, usuario_id, False)
    if conta is None:
        raise ValueError("Conta nao encontrada.")
    return _formatar_conta(conta)


def alterar_status_conta_service(conta_id: int, ativo: bool, usuario_id: int) -> dict:
    conta = obter_conta(conta_id, usuario_id, False)
    if conta is None:
        raise ValueError("Conta nao encontrada.")
    if not ativo and abs(float(conta[6])) >= 0.005:
        raise ValueError("Transfira ou ajuste o saldo antes de desativar esta conta.")
    alterar_status_conta(conta_id, ativo, usuario_id)
    atualizada = obter_conta(conta_id, usuario_id, False)
    if atualizada is None:
        raise ValueError("Conta nao encontrada.")
    return _formatar_conta(atualizada)


def definir_conta_principal_service(conta_id: int, usuario_id: int) -> dict:
    conta = obter_conta(conta_id, usuario_id, False)
    if conta is None:
        raise ValueError("Conta nao encontrada.")
    if not bool(conta[4]):
        raise ValueError("Uma conta inativa nao pode ser principal.")
    if not definir_conta_principal(conta_id, usuario_id):
        raise ValueError("Conta nao encontrada.")
    atualizada = obter_conta(conta_id, usuario_id, False)
    if atualizada is None:
        raise ValueError("Conta nao encontrada.")
    return _formatar_conta(atualizada)
