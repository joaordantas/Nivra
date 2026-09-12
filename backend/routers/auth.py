import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.auth import (
    CsrfResponse, EmailRequest, LoginRequest, MessageResponse, PasswordChangeRequest,
    PasswordResetRequest, RegisterRequest, TokenRequest, UserResponse,
)
from services.auth_service import alterar_senha_service, login, registrar
from services.auth_token_service import (
    VerificationCooldownError, redefinir_senha_service, solicitar_redefinicao_senha,
    solicitar_verificacao_email, verificar_email_service,
)
from services.rate_limit_service import (
    RateLimitExceeded, consumir_limite, hash_rate_subject, limpar_limite,
    registrar_falha, verificar_limite,
)
from services.session_service import (
    CSRF_COOKIE, SESSION_COOKIE, criar_sessao_service, cookie_is_secure,
    revogar_sessao_service, rotacionar_csrf_service, session_duration_seconds,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=session_duration_seconds(), httponly=False,
        secure=cookie_is_secure(), samesite="lax", path="/",
    )


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, session_token, max_age=session_duration_seconds(), httponly=True,
        secure=cookie_is_secure(), samesite="lax", path="/",
    )
    _set_csrf_cookie(response, csrf_token)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=cookie_is_secure(), samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=cookie_is_secure(), samesite="lax")


def _require_public_csrf(
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
) -> None:
    if not csrf_header or not csrf_cookie or not secrets.compare_digest(csrf_header, csrf_cookie):
        raise HTTPException(status_code=403, detail="Token CSRF ausente ou inválido.")


def _client_ip(request: Request) -> str:
    if os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV"):
        forwarded = request.headers.get("x-vercel-forwarded-for") or request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_key(request: Request, *identity: str) -> str:
    return hash_rate_subject(_client_ip(request), *identity)


def _raise_rate_limit(exc: RateLimitExceeded) -> None:
    raise HTTPException(
        status_code=429, detail="Muitas tentativas. Tente novamente mais tarde.",
        headers={"Retry-After": str(exc.retry_after)},
    ) from exc


@router.get("/csrf", response_model=CsrfResponse)
def get_csrf_token(request: Request, response: Response) -> CsrfResponse:
    csrf_token = rotacionar_csrf_service(request.cookies.get(SESSION_COOKIE), request.cookies.get(CSRF_COOKIE))
    _set_csrf_cookie(response, csrf_token)
    return CsrfResponse(csrf_token=csrf_token)


@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(_require_public_csrf)])
def register_user(payload: RegisterRequest, request: Request, response: Response, csrf_token: Annotated[str, Cookie(alias=CSRF_COOKIE)]) -> UserResponse:
    key = _rate_key(request)
    try:
        consumir_limite("register", key, 5, 3600)
        usuario_id = registrar(payload.usuario, payload.email, payload.senha, payload.tipo_perfil)
        solicitar_verificacao_email(usuario_id, respeitar_cooldown=False)
        resultado = login(payload.email, payload.senha)
        if resultado is None:
            raise HTTPException(status_code=500, detail="Não foi possível carregar o usuário criado.")
        session_token = criar_sessao_service(usuario_id, csrf_token)
        _set_session_cookies(response, session_token, csrf_token)
        return _user_from_tuple(resultado)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Usuário ou e-mail já cadastrado.") from exc


@router.post("/login", response_model=UserResponse, dependencies=[Depends(_require_public_csrf)])
def login_user(payload: LoginRequest, request: Request, response: Response, csrf_token: Annotated[str, Cookie(alias=CSRF_COOKIE)]) -> UserResponse:
    key = _rate_key(request, payload.email.lower())
    try:
        verificar_limite("login_failure", key, 8, 900)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    resultado = login(payload.email, payload.senha)
    if resultado is None:
        registrar_falha("login_failure", key)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    limpar_limite("login_failure", key)
    session_token = criar_sessao_service(int(resultado[0]), csrf_token)
    _set_session_cookies(response, session_token, csrf_token)
    return _user_from_tuple(resultado)


@router.get("/me", response_model=UserResponse)
def current_user(current_user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=current_user.id, usuario=current_user.usuario, email=current_user.email,
        tipo_perfil=current_user.tipo_perfil, email_verificado=current_user.email_verificado,
        email_verificado_em=current_user.email_verificado_em,
    )


@router.post("/email/verify", response_model=MessageResponse, dependencies=[Depends(_require_public_csrf)])
def verify_email(payload: TokenRequest, request: Request) -> MessageResponse:
    try:
        consumir_limite("verify_email", _rate_key(request), 10, 900)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    if not verificar_email_service(payload.token):
        raise HTTPException(status_code=400, detail="Link de verificação inválido, expirado ou já utilizado.")
    return MessageResponse(message="E-mail verificado com sucesso.")


@router.post("/email/resend", response_model=MessageResponse, status_code=202)
def resend_verification(request: Request, current_user: CurrentUserCsrf) -> MessageResponse:
    if current_user.email_verificado:
        return MessageResponse(message="Este e-mail já está verificado.")
    key = _rate_key(request, str(current_user.id))
    try:
        consumir_limite("resend_verification", key, 5, 3600)
        sent = solicitar_verificacao_email(current_user.id)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    except VerificationCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc
    if not sent:
        raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail agora. Tente novamente.")
    return MessageResponse(message="E-mail de verificação enviado.")


@router.post("/password/forgot", response_model=MessageResponse, status_code=202, dependencies=[Depends(_require_public_csrf)])
def forgot_password(payload: EmailRequest, request: Request) -> MessageResponse:
    try:
        consumir_limite("forgot_password", _rate_key(request, payload.email.lower()), 3, 3600)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    solicitar_redefinicao_senha(payload.email)
    return MessageResponse(message="Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação.")


@router.post("/password/reset", response_model=MessageResponse, dependencies=[Depends(_require_public_csrf)])
def reset_password(payload: PasswordResetRequest, request: Request, response: Response) -> MessageResponse:
    try:
        consumir_limite("reset_password", _rate_key(request), 10, 900)
        changed = redefinir_senha_service(payload.token, payload.nova_senha, payload.confirmar_senha)
    except RateLimitExceeded as exc:
        _raise_rate_limit(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=400, detail="Link de recuperação inválido, expirado ou já utilizado.")
    _clear_session_cookies(response)
    return MessageResponse(message="Senha redefinida. Entre novamente com a nova senha.")


@router.post("/password/change", response_model=MessageResponse)
def change_password(payload: PasswordChangeRequest, response: Response, csrf_token: Annotated[str, Cookie(alias=CSRF_COOKIE)], current_user: CurrentUserCsrf) -> MessageResponse:
    try:
        alterar_senha_service(current_user.id, payload.senha_atual, payload.nova_senha, payload.confirmar_senha)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_token = criar_sessao_service(current_user.id, csrf_token)
    _set_session_cookies(response, session_token, csrf_token)
    return MessageResponse(message="Senha alterada. As outras sessões foram encerradas.")


@router.post("/logout", status_code=204)
def logout_user(request: Request, response: Response, current_user: CurrentUserCsrf) -> None:
    del current_user
    revogar_sessao_service(request.cookies.get(SESSION_COOKIE))
    _clear_session_cookies(response)


def _user_from_tuple(usuario: tuple) -> UserResponse:
    return UserResponse(
        id=int(usuario[0]), usuario=str(usuario[1]), email=str(usuario[2]), tipo_perfil=str(usuario[4]),
        email_verificado=bool(usuario[5]),
        email_verificado_em=str(usuario[6]) if usuario[6] is not None else None,
    )
