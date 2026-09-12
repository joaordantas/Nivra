import bcrypt

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verificar_senha(senha: str, hash_salvo: str | bytes) -> bool:
    hash_bytes = hash_salvo.encode("utf-8") if isinstance(hash_salvo, str) else hash_salvo
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_bytes)
    except (ValueError, TypeError):
        return False
