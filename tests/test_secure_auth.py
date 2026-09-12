import os
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.db_support import remove_test_database, reset_test_database
from backend.main import app
from database.connection import get_connection
from repositories.sessao_repo import criar_sessao
from services.session_service import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    cookie_is_secure,
    hash_token,
)
from tests.auth_support import csrf_headers, issue_csrf, register_client


class SecureAuthenticationTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_protected_route_requires_a_server_session(self):
        response = self.client.get("/api/accounts")

        self.assertEqual(response.status_code, 401, response.text)

    def test_openapi_does_not_expose_user_id_as_a_client_parameter(self):
        document = json.dumps(app.openapi(), ensure_ascii=False)

        self.assertNotIn('"usuario_id"', document)

    def test_login_and_registration_require_public_csrf(self):
        register = self.client.post(
            "/api/auth/register",
            json={"usuario": "Sem CSRF", "email": "semcsrf@example.com", "senha": "senha123"},
        )
        login = self.client.post(
            "/api/auth/login",
            json={"email": "semcsrf@example.com", "senha": "senha123"},
        )

        self.assertEqual(register.status_code, 403, register.text)
        self.assertEqual(login.status_code, 403, login.text)

    def test_session_cookie_is_http_only_and_only_its_hash_is_persisted(self):
        response = self._register("Usuario Seguro", "seguro@example.com")
        raw_token = self.client.cookies.get(SESSION_COOKIE)
        set_cookie_headers = "\n".join(response.headers.get_list("set-cookie")).lower()

        self.assertIsNotNone(raw_token)
        self.assertIn("nivra_session=", set_cookie_headers)
        self.assertIn("httponly", set_cookie_headers)
        self.assertIn("samesite=lax", set_cookie_headers)

        conn = get_connection()
        try:
            row = conn.execute("SELECT token_hash FROM sessoes").fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], raw_token)
        self.assertEqual(row[0], hash_token(str(raw_token)))

    def test_me_restores_a_persisted_session_in_another_client(self):
        registered = register_client(self.client, "Persistente", "persistente@example.com")
        raw_token = self.client.cookies.get(SESSION_COOKIE)

        with TestClient(app) as another_client:
            another_client.cookies.set(SESSION_COOKIE, raw_token)
            response = another_client.get("/api/auth/me")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], registered["id"])

    def test_csrf_token_remains_stable_for_the_same_valid_session(self):
        register_client(self.client, "Duas Abas", "duas-abas@example.com")
        first_token = self.client.cookies.get(CSRF_COOKIE)

        response = self.client.get("/api/auth/csrf")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["csrf_token"], first_token)

    def test_mutations_require_the_csrf_bound_to_the_session(self):
        register_client(self.client, "CSRF", "csrf@example.com")

        missing = self.client.post(
            "/api/accounts",
            json={"nome": "Conta", "tipo": "digital", "saldo_inicial": 0},
        )
        invalid = self.client.post(
            "/api/accounts",
            headers={"X-CSRF-Token": "token-incorreto"},
            json={"nome": "Conta", "tipo": "digital", "saldo_inicial": 0},
        )
        valid = self.client.post(
            "/api/accounts",
            headers=csrf_headers(self.client),
            json={"nome": "Conta", "tipo": "digital", "saldo_inicial": 0},
        )

        self.assertEqual(missing.status_code, 403, missing.text)
        self.assertEqual(invalid.status_code, 403, invalid.text)
        self.assertEqual(valid.status_code, 201, valid.text)

    def test_logout_revokes_the_server_session(self):
        register_client(self.client, "Logout", "logout@example.com")
        raw_token = self.client.cookies.get(SESSION_COOKIE)

        logout = self.client.post("/api/auth/logout", headers=csrf_headers(self.client))
        me = self.client.get("/api/auth/me")

        self.assertEqual(logout.status_code, 204, logout.text)
        self.assertEqual(me.status_code, 401, me.text)

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT revogada_em FROM sessoes WHERE token_hash = ?",
                (hash_token(str(raw_token)),),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row[0])

    def test_expired_session_is_rejected_and_revoked(self):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Expirado', 'expirado@example.com', 'hash')"
            )
            conn.commit()
        finally:
            conn.close()

        raw_token = "expired-session-token"
        criar_sessao(
            1,
            hash_token(raw_token),
            hash_token("csrf-expirado"),
            datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.client.cookies.set(SESSION_COOKIE, raw_token)

        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 401, response.text)
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT revogada_em FROM sessoes WHERE token_hash = ?", (hash_token(raw_token),)
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row[0])

    def test_spoofed_user_id_cannot_change_the_session_identity(self):
        user_a = register_client(self.client, "Usuario A", "a@example.com")
        with TestClient(app) as client_b:
            register_client(client_b, "Usuario B", "b@example.com")
            own_account = client_b.post(
                "/api/accounts",
                headers=csrf_headers(client_b),
                json={"nome": "Conta B", "tipo": "digital", "saldo_inicial": 75},
            )
            self.assertEqual(own_account.status_code, 201, own_account.text)

        forged_body = self.client.post(
            "/api/accounts",
            headers=csrf_headers(self.client),
            json={
                "nome": "Forjada",
                "tipo": "digital",
                "saldo_inicial": 0,
                "usuario_id": user_a["id"] + 1,
            },
        )
        forged_query = self.client.get("/api/accounts", params={"usuario_id": user_a["id"] + 1})

        self.assertEqual(forged_body.status_code, 422, forged_body.text)
        self.assertEqual(forged_query.status_code, 200, forged_query.text)
        self.assertEqual(forged_query.json(), [])

    def test_cors_allows_the_local_app_and_does_not_authorize_an_unknown_origin(self):
        allowed = self.client.options(
            "/api/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = self.client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://malicious.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertNotEqual(denied.headers.get("access-control-allow-origin"), "https://malicious.example")

    def test_session_cookie_is_secure_only_in_production(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            self.assertTrue(cookie_is_secure())
        with patch.dict(os.environ, {"APP_ENV": "development", "VERCEL_ENV": "production"}):
            self.assertTrue(cookie_is_secure())
        with patch.dict(os.environ, {"APP_ENV": "development", "VERCEL_ENV": "preview"}):
            self.assertFalse(cookie_is_secure())

    def _register(self, name: str, email: str):
        csrf_token = issue_csrf(self.client)
        response = self.client.post(
            "/api/auth/register",
            headers={"X-CSRF-Token": csrf_token},
            json={"usuario": name, "email": email, "senha": "senha-segura-123"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response


if __name__ == "__main__":
    unittest.main()
