import re
from datetime import datetime, timezone

from repositories.usuario_repo import (
    atualizar_senha_e_revogar_acessos,
    buscar_perfil,
    buscar_usuario_por_email,
    buscar_usuario_por_id,
    cadastrar_usuario,
)
from utils.security import hash_senha, verificar_senha


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 72


def _validar_email(email: str) -> bool:
    padrao = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(padrao, email))


def validar_senha_nova(senha: str) -> None:
    if len(senha) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(senha.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("A senha deve ter no máximo 72 bytes.")


def registrar(usuario: str, email: str, senha: str, tipo_perfil: str) -> int:
    email_normalizado = email.strip().lower()
    if not _validar_email(email_normalizado):
        raise ValueError("E-mail inválido. Use o formato: nome@exemplo.com")
    validar_senha_nova(senha)
    return cadastrar_usuario(usuario.strip(), email_normalizado, senha, tipo_perfil)


def login(email: str, senha: str):
    usuario = buscar_usuario_por_email(email.strip().lower())
    if usuario is None:
        return None
    if verificar_senha(senha, usuario[3]):
        return usuario
    return None


def alterar_senha_service(
    usuario_id: int,
    senha_atual: str,
    nova_senha: str,
    confirmar_senha: str,
) -> None:
    if nova_senha != confirmar_senha:
        raise ValueError("A confirmação da nova senha não corresponde.")
    validar_senha_nova(nova_senha)
    usuario = buscar_usuario_por_id(usuario_id)
    if usuario is None or not verificar_senha(senha_atual, usuario[3]):
        raise ValueError("A senha atual está incorreta.")
    if verificar_senha(nova_senha, usuario[3]):
        raise ValueError("A nova senha deve ser diferente da senha atual.")
    atualizar_senha_e_revogar_acessos(
        usuario_id,
        hash_senha(nova_senha),
        datetime.now(timezone.utc),
    )


def obter_perfil(usuario_id: int) -> str | None:
    return buscar_perfil(usuario_id)
