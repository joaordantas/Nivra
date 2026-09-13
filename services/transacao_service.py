import json
from collections import Counter
from datetime import date
from decimal import Decimal

from repositories.categoria_repo import listar_categorias_sistema
from repositories.transacao_repo import (
    adicionar_transacao,
    atualizar_transacao,
    buscar_transacao_por_id,
    calcular_total_compras_cartao,
    deletar_transacao,
    listar_transacoes,
    listar_transacoes_bancarias_vinculadas,
)
from services.categoria_service import obter_categoria
from services.conta_service import obter_conta_ativa
from services.finance_validations import limpar_descricao, validar_data_financeira
from services.open_finance_reconciliation_service import (
    detectar_candidatos_conciliacao_service,
)
from utils.categorias_padrao import (
    DEFAULT_CATEGORY_KEYS,
    is_provider_neutral_movement,
    map_provider_category,
)


def _validar_transacao(
    valor: float,
    tipo: str,
    categoria_id: int | None,
    data: str,
    usuario_id: int,
    conta_id: int | None,
) -> None:
    if valor <= 0:
        raise ValueError("O valor da transacao deve ser maior que zero.")
    if tipo not in {"entrada", "saida"}:
        raise ValueError("Tipo de transacao invalido.")
    validar_data_financeira(data)
    if conta_id is not None and obter_conta_ativa(conta_id, usuario_id) is None:
        raise ValueError("Conta nao encontrada.")
    if categoria_id is not None and obter_categoria(categoria_id, usuario_id) is None:
        raise ValueError("Categoria nao encontrada.")


def _formatar_transacao(transacao: tuple) -> dict:
    (
        transacao_id,
        valor,
        tipo,
        categoria_id,
        categoria,
        comentario,
        data,
        conta_id,
        conta,
        transacao_bancaria_id,
        instituicao_nome,
        ultima_sincronizacao_em,
    ) = transacao
    return {
        "id": transacao_id,
        "valor": float(valor),
        "tipo": tipo,
        "categoria_id": categoria_id,
        "categoria": categoria,
        "comentario": comentario,
        "data": data,
        "conta_id": conta_id,
        "conta": conta,
        "origem": "manual",
        "editavel": True,
        "status_conciliacao": "conciliada" if transacao_bancaria_id is not None else None,
        "transacao_nivra_id": None,
        "conciliada_com_banco": transacao_bancaria_id is not None,
        "neutra": False,
        "instituicao_nome": instituicao_nome,
        "ultima_sincronizacao_em": (
            str(ultima_sincronizacao_em)
            if ultima_sincronizacao_em is not None
            else None
        ),
    }


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


def _categoria_externa(metadata: dict) -> str:
    stored_key = metadata.get("nivra_category_key")
    if isinstance(stored_key, str) and stored_key in DEFAULT_CATEGORY_KEYS:
        return stored_key
    return map_provider_category(
        "pluggy",
        metadata.get("category_id"),
        metadata.get("category_name"),
    )


def _formatar_transacao_bancaria(
    transacao: tuple,
    categorias: dict[str, tuple[int, str]],
) -> dict:
    (
        transacao_id,
        valor,
        direcao,
        descricao,
        data_transacao,
        conta_id,
        conta,
        metadata_raw,
        status_conciliacao,
        transacao_nivra_id,
        instituicao_nome,
        ultima_sincronizacao_em,
    ) = transacao
    metadata = _metadata(metadata_raw)
    categoria_chave = _categoria_externa(metadata)
    categoria_id, categoria_nome = categorias.get(
        categoria_chave,
        categorias.get("other", (None, "Outros")),
    )
    return {
        "id": int(transacao_id),
        "valor": float(valor),
        "tipo": str(direcao),
        "categoria_id": categoria_id,
        "categoria": categoria_nome,
        "comentario": str(descricao),
        "data": str(data_transacao),
        "conta_id": int(conta_id),
        "conta": str(conta),
        "origem": "open_finance",
        "editavel": False,
        "status_conciliacao": str(status_conciliacao),
        "transacao_nivra_id": (
            int(transacao_nivra_id) if transacao_nivra_id is not None else None
        ),
        "conciliada_com_banco": False,
        "neutra": is_provider_neutral_movement(
            "pluggy",
            metadata.get("category_id"),
            metadata.get("category_name"),
        ),
        "instituicao_nome": str(instituicao_nome),
        "ultima_sincronizacao_em": (
            str(ultima_sincronizacao_em)
            if ultima_sincronizacao_em is not None
            else None
        ),
        "_categoria_chave": categoria_chave,
    }


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _marcar_transferencias_internas(transacoes: list[dict]) -> None:
    bancarias = [
        transacao
        for transacao in transacoes
        if transacao["origem"] == "open_finance"
        and transacao.get("_categoria_chave") == "transfers"
    ]
    saidas = [item for item in bancarias if item["tipo"] == "saida"]
    entradas = [item for item in bancarias if item["tipo"] == "entrada"]
    candidatas: dict[int, list[int]] = {}
    entradas_por_id = {item["id"]: item for item in entradas}
    for saida in saidas:
        matches = [
            entrada["id"]
            for entrada in entradas
            if entrada["conta_id"] != saida["conta_id"]
            and _money(entrada["valor"]) == _money(saida["valor"])
            and abs((_date(entrada["data"]) - _date(saida["data"])).days) <= 1
        ]
        if len(matches) == 1:
            candidatas[saida["id"]] = matches
    ocorrencias_entrada = Counter(ids[0] for ids in candidatas.values())
    saidas_por_id = {item["id"]: item for item in saidas}
    for saida_id, entrada_ids in candidatas.items():
        entrada_id = entrada_ids[0]
        if ocorrencias_entrada[entrada_id] == 1:
            saidas_por_id[saida_id]["neutra"] = True
            entradas_por_id[entrada_id]["neutra"] = True


def criar_transacao_service(
    valor: float,
    tipo: str,
    categoria_id: int | None,
    comentario: str | None,
    data: str,
    usuario_id: int,
    conta_id: int | None = None,
) -> dict:
    _validar_transacao(valor, tipo, categoria_id, data, usuario_id, conta_id)
    transacao_id = adicionar_transacao(
        valor,
        tipo,
        categoria_id,
        limpar_descricao(comentario),
        data,
        usuario_id,
        conta_id,
    )
    transacao = buscar_transacao_por_id(transacao_id, usuario_id)
    if transacao is None:
        raise ValueError("Transacao nao encontrada.")
    detectar_candidatos_conciliacao_service(usuario_id)
    return _formatar_transacao(transacao)


def atualizar_transacao_service(
    transacao_id: int,
    valor: float,
    tipo: str,
    categoria_id: int | None,
    comentario: str | None,
    data: str,
    usuario_id: int,
    conta_id: int | None,
) -> dict:
    if buscar_transacao_por_id(transacao_id, usuario_id) is None:
        raise ValueError("Transacao nao encontrada.")
    _validar_transacao(valor, tipo, categoria_id, data, usuario_id, conta_id)
    atualizar_transacao(
        transacao_id,
        valor,
        tipo,
        categoria_id,
        limpar_descricao(comentario),
        data,
        conta_id,
        usuario_id,
    )
    transacao = buscar_transacao_por_id(transacao_id, usuario_id)
    if transacao is None:
        raise ValueError("Transacao nao encontrada.")
    detectar_candidatos_conciliacao_service(usuario_id)
    return _formatar_transacao(transacao)


def deletar_transacao_service(transacao_id: int, usuario_id: int) -> bool:
    deleted = deletar_transacao(transacao_id, usuario_id)
    if deleted:
        detectar_candidatos_conciliacao_service(usuario_id)
    return deleted


def listar_transacoes_formatadas(
    usuario_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[dict]:
    categorias = {
        str(chave): (int(categoria_id), str(nome))
        for categoria_id, nome, chave in listar_categorias_sistema(usuario_id)
    }
    manuais = [
        _formatar_transacao(transacao)
        for transacao in listar_transacoes(usuario_id, data_inicio, data_fim)
    ]
    bancarias = [
        _formatar_transacao_bancaria(transacao, categorias)
        for transacao in listar_transacoes_bancarias_vinculadas(
            usuario_id,
        )
    ]
    todas = [*manuais, *bancarias]
    _marcar_transferencias_internas(todas)
    if data_inicio is not None:
        todas = [item for item in todas if str(item["data"]) >= data_inicio]
    if data_fim is not None:
        todas = [item for item in todas if str(item["data"]) <= data_fim]
    for transacao in todas:
        transacao.pop("_categoria_chave", None)
    return sorted(
        todas,
        key=lambda transacao: (
            str(transacao["data"]),
            1 if transacao["origem"] == "open_finance" else 0,
            int(transacao["id"]),
        ),
        reverse=True,
    )


def obter_resumo_financeiro(
    usuario_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict:
    transacoes = listar_transacoes_formatadas(usuario_id, data_inicio, data_fim)
    entradas_decimal = sum(
        (
            _money(item["valor"])
            for item in transacoes
            if item["tipo"] == "entrada" and not item["neutra"]
        ),
        Decimal("0.00"),
    )
    saidas_decimal = sum(
        (
            _money(item["valor"])
            for item in transacoes
            if item["tipo"] == "saida" and not item["neutra"]
        ),
        Decimal("0.00"),
    )
    entradas = float(entradas_decimal)
    saidas = float(saidas_decimal) + calcular_total_compras_cartao(
        usuario_id,
        data_inicio,
        data_fim,
    )
    saldo = entradas - saidas
    return {"entradas": entradas, "saidas": saidas, "saldo": saldo}
