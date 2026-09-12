from typing import Literal

from pydantic import BaseModel


class ConnectTokenResponse(BaseModel):
    connect_token: str
    provider: Literal["pluggy"] = "pluggy"
    environment: Literal["sandbox"] = "sandbox"

