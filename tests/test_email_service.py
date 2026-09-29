import json
import os
import unittest
from unittest.mock import patch

from services.email_service import (
    EmailDeliveryError,
    MemoryEmailProvider,
    enviar_redefinicao_senha,
    enviar_verificacao_email,
    set_email_provider_for_tests,
)
from services.session_service import hash_token


class _SuccessfulResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class EmailServiceTests(unittest.TestCase):
    def tearDown(self):
        set_email_provider_for_tests(None)

    def test_memory_provider_stores_verification_text_and_html(self):
        provider = MemoryEmailProvider()
        set_email_provider_for_tests(provider)

        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "APP_PUBLIC_URL": "https://nivra.example"},
        ):
            enviar_verificacao_email("cliente@example.com", "token-seguro")

        self.assertEqual(len(provider.outbox), 1)
        message = provider.outbox[0]
        link = "https://nivra.example/verify-email#token=token-seguro"
        self.assertEqual(message.recipient, "cliente@example.com")
        self.assertEqual(message.subject, "Confirme seu e-mail na Nivra")
        self.assertIn(link, message.text)
        self.assertIn(link, message.html)
        self.assertIn("Verificar meu e-mail", message.html)
        self.assertIn("Nivra · Seu dinheiro, mais claro", message.html)
        self.assertIn("24 horas", message.text)
        self.assertEqual(message.idempotency_key, f"verify-{hash_token('token-seguro')}")

    def test_memory_provider_stores_password_reset_text_and_html(self):
        provider = MemoryEmailProvider()
        set_email_provider_for_tests(provider)

        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "APP_PUBLIC_URL": "https://nivra.example"},
        ):
            enviar_redefinicao_senha("cliente@example.com", "reset-seguro")

        message = provider.outbox[0]
        link = "https://nivra.example/reset-password#token=reset-seguro"
        self.assertEqual(message.subject, "Redefina sua senha da Nivra")
        self.assertIn(link, message.text)
        self.assertIn(link, message.html)
        self.assertIn("Criar nova senha", message.html)
        self.assertIn("Sua senha continuará a mesma", message.text)
        self.assertIn("Sua senha continuará a mesma", message.html)
        self.assertEqual(message.idempotency_key, f"reset-{hash_token('reset-seguro')}")

    @patch("services.email_service.urlopen", return_value=_SuccessfulResponse())
    def test_resend_payload_contains_text_html_recipient_and_idempotency(self, mocked_urlopen):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "Nivra <conta@nivra.com>",
                "APP_PUBLIC_URL": "https://nivra.example",
            },
            clear=True,
        ):
            enviar_verificacao_email("destino@example.com", "token-resend")

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["from"], "Nivra <conta@nivra.com>")
        self.assertEqual(payload["to"], ["destino@example.com"])
        self.assertEqual(payload["subject"], "Confirme seu e-mail na Nivra")
        self.assertIn("verify-email#token=token-resend", payload["text"])
        self.assertIn("verify-email#token=token-resend", payload["html"])
        self.assertEqual(
            request.get_header("Idempotency-key"),
            f"verify-{hash_token('token-resend')}",
        )
        mocked_urlopen.assert_called_once_with(request, timeout=10)

    def test_production_rejects_missing_or_unsafe_configuration(self):
        cases = [
            {
                "APP_ENV": "production",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "Nivra <conta@nivra.com>",
                "APP_PUBLIC_URL": "https://nivra.example",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "APP_PUBLIC_URL": "https://nivra.example",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "memory",
                "APP_PUBLIC_URL": "https://nivra.example",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "Nivra <conta@nivra.com>",
                "APP_PUBLIC_URL": "http://nivra.example",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "Nivra <conta@nivra.com>",
                "APP_PUBLIC_URL": "https://nivra.example/path?redirect=evil",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "remetente-invalido",
                "APP_PUBLIC_URL": "https://nivra.example",
            },
            {
                "APP_ENV": "production",
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "re_test_key",
                "EMAIL_FROM": "Nivra <conta@nivra.com>",
            },
        ]

        for environment in cases:
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(EmailDeliveryError):
                        enviar_verificacao_email("destino@example.com", "token-seguro")

    def test_html_escapes_every_dynamic_value(self):
        provider = MemoryEmailProvider()
        set_email_provider_for_tests(provider)
        with patch.dict(
            os.environ,
            {"APP_ENV": "development", "APP_PUBLIC_URL": "https://nivra.example"},
        ):
            enviar_verificacao_email("destino@example.com", "<script>alert('x')</script>")

        message = provider.outbox[0]
        self.assertNotIn("<script>", message.html)
        self.assertIn("%3Cscript%3E", message.html)


if __name__ == "__main__":
    unittest.main()
