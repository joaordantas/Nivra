import re
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.email_service import (
    EmailDeliveryError,
    MemoryEmailProvider,
    set_email_provider_for_tests,
)
from services.session_service import SESSION_COOKIE, hash_token
from tests.auth_support import csrf_headers, issue_csrf, register_client
from tests.db_support import remove_test_database, reset_test_database


PASSWORD = "senha-segura-123"
NEW_PASSWORD = "uma-nova-senha-456"


class FailingEmailProvider:
    def send(self, message) -> None:
        del message
        raise EmailDeliveryError("Falha simulada e segura.")


class AccountHardeningTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.mail = MemoryEmailProvider()
        set_email_provider_for_tests(self.mail)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        set_email_provider_for_tests(None)
        remove_test_database()

    def _token_from_last_email(self) -> str:
        match = re.search(r"#token=([^\s]+)", self.mail.outbox[-1].text)
        self.assertIsNotNone(match)
        return str(match.group(1))

    def _post_public(self, path: str, payload: dict):
        token = issue_csrf(self.client)
        return self.client.post(path, headers={"X-CSRF-Token": token}, json=payload)

    def test_registration_enforces_strong_password_and_sends_verification(self):
        weak = self._post_public(
            "/api/auth/register",
            {"usuario": "Fraco", "email": "fraco@example.com", "senha": "curta123"},
        )
        user = register_client(self.client, "Seguro", "seguro@example.com")

        self.assertEqual(weak.status_code, 422, weak.text)
        self.assertFalse(user["email_verificado"])
        self.assertTrue(user["verification_email_sent"])
        self.assertEqual(len(self.mail.outbox), 1)

        raw_token = self._token_from_last_email()
        conn = get_connection()
        try:
            stored = conn.execute("SELECT token_hash FROM auth_tokens").fetchone()[0]
        finally:
            conn.close()
        self.assertNotEqual(stored, raw_token)
        self.assertEqual(stored, hash_token(raw_token))

    def test_registration_succeeds_when_email_delivery_fails(self):
        set_email_provider_for_tests(FailingEmailProvider())

        response = self._post_public(
            "/api/auth/register",
            {"usuario": "Sem envio", "email": "sem-envio@example.com", "senha": PASSWORD},
        )
        me = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertFalse(response.json()["verification_email_sent"])
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], "sem-envio@example.com")
        conn = get_connection()
        try:
            token = conn.execute(
                "SELECT usado_em, revogado_em FROM auth_tokens"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(token)
        self.assertIsNone(token[0])
        self.assertIsNotNone(token[1])

    def test_email_verification_is_single_use_and_updates_current_session(self):
        register_client(self.client, "Verificar", "verificar@example.com")
        raw_token = self._token_from_last_email()

        first = self._post_public("/api/auth/email/verify", {"token": raw_token})
        second = self._post_public("/api/auth/email/verify", {"token": raw_token})
        me = self.client.get("/api/auth/me")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 400, second.text)
        self.assertTrue(me.json()["email_verificado"])
        self.assertIsNotNone(me.json()["email_verificado_em"])

    def test_expired_email_verification_token_is_rejected(self):
        register_client(self.client, "Expirado", "verify-expirado@example.com")
        raw_token = self._token_from_last_email()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_tokens SET expira_em = ? WHERE token_hash = ?",
                (datetime.now(timezone.utc) - timedelta(minutes=1), hash_token(raw_token)),
            )
            conn.commit()
        finally:
            conn.close()

        response = self._post_public("/api/auth/email/verify", {"token": raw_token})
        self.assertEqual(response.status_code, 400, response.text)

    def test_resend_enforces_cooldown_then_replaces_previous_token(self):
        register_client(self.client, "Reenvio", "reenvio@example.com")
        first_token = self._token_from_last_email()
        blocked = self.client.post(
            "/api/auth/email/resend", headers=csrf_headers(self.client)
        )
        self.assertEqual(blocked.status_code, 429, blocked.text)
        self.assertIn("Retry-After", blocked.headers)

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_tokens SET criado_em = ? WHERE token_hash = ?",
                (datetime.now(timezone.utc) - timedelta(minutes=2), hash_token(first_token)),
            )
            conn.commit()
        finally:
            conn.close()

        sent = self.client.post(
            "/api/auth/email/resend", headers=csrf_headers(self.client)
        )
        second_token = self._token_from_last_email()
        old_link = self._post_public("/api/auth/email/verify", {"token": first_token})

        self.assertEqual(sent.status_code, 202, sent.text)
        self.assertNotEqual(first_token, second_token)
        self.assertEqual(old_link.status_code, 400, old_link.text)

    def test_resend_returns_safe_error_and_revokes_token_when_delivery_fails(self):
        register_client(self.client, "Falha reenvio", "falha-reenvio@example.com")
        first_token = self._token_from_last_email()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_tokens SET criado_em = ? WHERE token_hash = ?",
                (datetime.now(timezone.utc) - timedelta(minutes=2), hash_token(first_token)),
            )
            conn.commit()
        finally:
            conn.close()
        set_email_provider_for_tests(FailingEmailProvider())

        response = self.client.post(
            "/api/auth/email/resend", headers=csrf_headers(self.client)
        )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("simulada", response.text)
        conn = get_connection()
        try:
            active = conn.execute(
                """
                SELECT COUNT(*) FROM auth_tokens
                WHERE finalidade = 'email_verification'
                  AND usado_em IS NULL AND revogado_em IS NULL
                """
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(active, 0)

    def test_forgot_password_does_not_reveal_account_existence(self):
        register_client(self.client, "Existente", "existe@example.com")
        existing = self._post_public("/api/auth/password/forgot", {"email": "existe@example.com"})
        missing = self._post_public("/api/auth/password/forgot", {"email": "nao-existe@example.com"})

        self.assertEqual(existing.status_code, 202, existing.text)
        self.assertEqual(missing.status_code, 202, missing.text)
        self.assertEqual(existing.json(), missing.json())

    def test_forgot_password_keeps_generic_response_when_delivery_fails(self):
        register_client(self.client, "Falha reset", "falha-reset@example.com")
        set_email_provider_for_tests(FailingEmailProvider())

        response = self._post_public(
            "/api/auth/password/forgot", {"email": "falha-reset@example.com"}
        )

        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(
            response.json()["message"],
            "Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação.",
        )
        conn = get_connection()
        try:
            active = conn.execute(
                """
                SELECT COUNT(*) FROM auth_tokens
                WHERE finalidade = 'password_reset'
                  AND usado_em IS NULL AND revogado_em IS NULL
                """
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(active, 0)

    def test_new_password_reset_request_revokes_the_previous_link(self):
        register_client(self.client, "Revogar reset", "revogar-reset@example.com")
        self._post_public(
            "/api/auth/password/forgot", {"email": "revogar-reset@example.com"}
        )
        first_token = self._token_from_last_email()
        self._post_public(
            "/api/auth/password/forgot", {"email": "revogar-reset@example.com"}
        )
        second_token = self._token_from_last_email()

        old_link = self._post_public(
            "/api/auth/password/reset",
            {
                "token": first_token,
                "nova_senha": NEW_PASSWORD,
                "confirmar_senha": NEW_PASSWORD,
            },
        )
        new_link = self._post_public(
            "/api/auth/password/reset",
            {
                "token": second_token,
                "nova_senha": NEW_PASSWORD,
                "confirmar_senha": NEW_PASSWORD,
            },
        )

        self.assertNotEqual(first_token, second_token)
        self.assertEqual(old_link.status_code, 400, old_link.text)
        self.assertEqual(new_link.status_code, 200, new_link.text)

    def test_password_reset_is_single_use_and_revokes_sessions(self):
        register_client(self.client, "Recuperar", "recuperar@example.com")
        old_session = self.client.cookies.get(SESSION_COOKIE)
        self._post_public("/api/auth/password/forgot", {"email": "recuperar@example.com"})
        raw_token = self._token_from_last_email()

        reset = self._post_public(
            "/api/auth/password/reset",
            {"token": raw_token, "nova_senha": NEW_PASSWORD, "confirmar_senha": NEW_PASSWORD},
        )
        reused = self._post_public(
            "/api/auth/password/reset",
            {"token": raw_token, "nova_senha": "terceira-senha-789", "confirmar_senha": "terceira-senha-789"},
        )
        with TestClient(app) as old_client:
            old_client.cookies.set(SESSION_COOKIE, old_session)
            old_me = old_client.get("/api/auth/me")
        old_login = self._post_public("/api/auth/login", {"email": "recuperar@example.com", "senha": PASSWORD})
        new_login = self._post_public("/api/auth/login", {"email": "recuperar@example.com", "senha": NEW_PASSWORD})

        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reused.status_code, 400, reused.text)
        self.assertEqual(old_me.status_code, 401, old_me.text)
        self.assertEqual(old_login.status_code, 401, old_login.text)
        self.assertEqual(new_login.status_code, 200, new_login.text)

    def test_expired_password_reset_token_is_rejected(self):
        register_client(self.client, "Expirado", "reset-expirado@example.com")
        self._post_public("/api/auth/password/forgot", {"email": "reset-expirado@example.com"})
        raw_token = self._token_from_last_email()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_tokens SET expira_em = ? WHERE token_hash = ?",
                (datetime.now(timezone.utc) - timedelta(minutes=1), hash_token(raw_token)),
            )
            conn.commit()
        finally:
            conn.close()

        response = self._post_public(
            "/api/auth/password/reset",
            {"token": raw_token, "nova_senha": NEW_PASSWORD, "confirmar_senha": NEW_PASSWORD},
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_authenticated_password_change_keeps_current_device_and_revokes_others(self):
        register_client(self.client, "Trocar", "trocar@example.com")
        old_session = self.client.cookies.get(SESSION_COOKIE)
        other = TestClient(app)
        other.cookies.set(SESSION_COOKIE, old_session)

        changed = self.client.post(
            "/api/auth/password/change",
            headers=csrf_headers(self.client),
            json={"senha_atual": PASSWORD, "nova_senha": NEW_PASSWORD, "confirmar_senha": NEW_PASSWORD},
        )
        current_me = self.client.get("/api/auth/me")
        other_me = other.get("/api/auth/me")
        other.close()

        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(current_me.status_code, 200, current_me.text)
        self.assertEqual(other_me.status_code, 401, other_me.text)

    def test_failed_logins_and_recovery_requests_are_rate_limited(self):
        register_client(self.client, "Limite", "limite@example.com")
        for _ in range(8):
            response = self._post_public("/api/auth/login", {"email": "limite@example.com", "senha": "incorreta"})
            self.assertEqual(response.status_code, 401, response.text)
        blocked_login = self._post_public("/api/auth/login", {"email": "limite@example.com", "senha": "incorreta"})

        for _ in range(3):
            response = self._post_public("/api/auth/password/forgot", {"email": "limite@example.com"})
            self.assertEqual(response.status_code, 202, response.text)
        blocked_recovery = self._post_public("/api/auth/password/forgot", {"email": "limite@example.com"})

        self.assertEqual(blocked_login.status_code, 429, blocked_login.text)
        self.assertIn("Retry-After", blocked_login.headers)
        self.assertEqual(blocked_recovery.status_code, 429, blocked_recovery.text)


if __name__ == "__main__":
    unittest.main()
