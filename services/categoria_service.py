from repositories.categoria_repo import (
    buscar_categoria_por_id,
    categoria_em_uso,
    criar_categoria,
    deletar_categoria,
    listar_categorias,
    nome_categoria_existe,
    renomear_categoria,
)


def listar_categorias_formatadas(usuario_id: int) -> list[dict]:
    return [
        {"id": categoria_id, "nome": nome, "padrao": chave_sistema is not None}
        for categoria_id, nome, chave_sistema in listar_categorias(usuario_id)
    ]


def obter_categoria(categoria_id: int, usuario_id: int) -> tuple | None:
    return buscar_categoria_por_id(categoria_id, usuario_id)


def criar_categoria_service(nome: str, usuario_id: int) -> dict:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("Digite um nome para a categoria.")
    if nome_categoria_existe(nome_limpo, usuario_id):
        raise ValueError("Ja existe uma categoria com esse nome.")
    categoria_id = criar_categoria(nome_limpo, usuario_id)
    return {"id": categoria_id, "nome": nome_limpo, "padrao": False}


def renomear_categoria_service(categoria_id: int, novo_nome: str, usuario_id: int) -> dict:
    nome_limpo = novo_nome.strip()
    if not nome_limpo:
        raise ValueError("Digite um novo nome para a categoria.")
    categoria = buscar_categoria_por_id(categoria_id, usuario_id)
    if categoria is None:
        raise ValueError("Categoria nao encontrada.")
    if nome_categoria_existe(nome_limpo, usuario_id, categoria_id):
        raise ValueError("Ja existe uma categoria com esse nome.")
    renomear_categoria(categoria_id, nome_limpo, usuario_id)
    return {"id": categoria_id, "nome": nome_limpo, "padrao": categoria[2] is not None}


def deletar_categoria_service(categoria_id: int, usuario_id: int) -> bool:
    categoria = buscar_categoria_por_id(categoria_id, usuario_id)
    if categoria is None:
        return False
    if categoria[2] is not None:
        raise ValueError("Categorias padrão não podem ser excluídas.")
    if categoria_em_uso(categoria_id, usuario_id):
        raise ValueError("Esta categoria esta em uso e nao pode ser excluida.")
    return deletar_categoria(categoria_id, usuario_id)
