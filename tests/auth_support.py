from fastapi.testclient import TestClient

from services.session_service import CSRF_COOKIE, SESSION_COOKIE, criar_sessao_service


def issue_csrf(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    if response.status_code != 200:
        raise AssertionError(response.text)
    return str(response.json()["csrf_token"])


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    if not token:
        token = issue_csrf(client)
    return {"X-CSRF-Token": str(token)}


def register_client(client: TestClient, name: str, email: str, password: str = "senha-segura-123") -> dict:
    token = issue_csrf(client)
    response = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json={"usuario": name, "email": email, "senha": password},
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()


def authenticate_existing_user(client: TestClient, user_id: int) -> dict[str, str]:
    csrf_token = "csrf-token-for-tests"
    session_token = criar_sessao_service(user_id, csrf_token)
    client.cookies.set(SESSION_COOKIE, session_token)
    client.cookies.set(CSRF_COOKIE, csrf_token)
    return {"X-CSRF-Token": csrf_token}
