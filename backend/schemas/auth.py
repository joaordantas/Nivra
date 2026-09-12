from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    senha: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str = Field(min_length=2, max_length=50)
    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)
    tipo_perfil: str = Field(default="Apenas Financeiro")


class UserResponse(BaseModel):
    id: int
    usuario: str
    email: EmailStr
    tipo_perfil: str
    email_verificado: bool
    email_verificado_em: str | None = None


class CsrfResponse(BaseModel):
    csrf_token: str


class MessageResponse(BaseModel):
    message: str


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=256)


class PasswordResetRequest(TokenRequest):
    nova_senha: str = Field(min_length=12, max_length=128)
    confirmar_senha: str = Field(min_length=12, max_length=128)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=12, max_length=128)
    confirmar_senha: str = Field(min_length=12, max_length=128)
