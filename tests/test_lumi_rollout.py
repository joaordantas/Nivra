import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.lumi import get_lumi_orchestrator
from database.connection import get_connection
from services.lumi_rollout_service import (
    lumi_access_allowed,
    lumi_rollout_mode,
    lumi_rollout_user_ids,
)
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database


ROLLOUT_KEYS = ("LUMI_PUBLIC_ENABLED", "LUMI_ROLLOUT_MODE", "LUMI_ROLLOUT_USER_IDS")


class LumiRolloutTests(unittest.TestCase):
    def setUp(self):
        self.previous = {key: os.environ.get(key) for key in ROLLOUT_KEYS}
        for key in ROLLOUT_KEYS:
            os.environ.pop(key, None)
        reset_test_database()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Interna', 'internal@example.com', 'hash')")
            conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Externa', 'external@example.com', 'hash')")
            conn.commit()
        finally:
            conn.close()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        remove_test_database()

    def test_master_and_rollout_modes_are_fail_closed(self):
        cases = (
            ({}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "invalid", "LUMI_ROLLOUT_MODE": "all"}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "false", "LUMI_ROLLOUT_MODE": "all"}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "true"}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "true", "LUMI_ROLLOUT_MODE": "invalid"}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "true", "LUMI_ROLLOUT_MODE": "off"}, "off", False),
            ({"LUMI_PUBLIC_ENABLED": "true", "LUMI_ROLLOUT_MODE": "all"}, "all", True),
        )
        for config, expected_mode, expected_access in cases:
            with self.subTest(config=config):
                for key in ROLLOUT_KEYS:
                    os.environ.pop(key, None)
                os.environ.update(config)
                self.assertEqual(lumi_rollout_mode(), expected_mode)
                self.assertEqual(lumi_access_allowed(1), expected_access)

    def test_allowlist_is_strict_and_uses_authenticated_user(self):
        os.environ.update({
            "LUMI_PUBLIC_ENABLED": "true",
            "LUMI_ROLLOUT_MODE": "allowlist",
            "LUMI_ROLLOUT_USER_IDS": "1, 3",
        })
        self.assertEqual(lumi_rollout_user_ids(), frozenset({1, 3}))
        self.assertTrue(lumi_access_allowed(1))
        self.assertFalse(lumi_access_allowed(2))
        os.environ["LUMI_ROLLOUT_USER_IDS"] = "1,invalid"
        self.assertEqual(lumi_rollout_user_ids(), frozenset())
        self.assertFalse(lumi_access_allowed(1))

    def test_direct_api_access_is_refused_outside_rollout(self):
        os.environ.update({
            "LUMI_PUBLIC_ENABLED": "true",
            "LUMI_ROLLOUT_MODE": "internal",
            "LUMI_ROLLOUT_USER_IDS": "1",
        })
        provider = Mock(return_value=SimpleNamespace(message="Olá!", tools_used=()))
        app.dependency_overrides[get_lumi_orchestrator] = lambda: SimpleNamespace(respond=provider)

        internal = TestClient(app)
        external = TestClient(app)
        try:
            internal_headers = authenticate_existing_user(internal, 1)
            external_headers = authenticate_existing_user(external, 2)
            self.assertEqual(internal.get("/api/lumi/capabilities").json(), {"public_enabled": True})
            self.assertEqual(external.get("/api/lumi/capabilities").json(), {"public_enabled": False})
            self.assertEqual(external.get("/api/lumi/conversations").status_code, 503)
            self.assertEqual(
                external.post("/api/lumi/message", headers=external_headers, json={"message": "oi"}).status_code,
                503,
            )
            self.assertEqual(
                external.post(
                    "/api/lumi/message",
                    headers=external_headers,
                    json={"message": "oi", "usuario_id": 1},
                ).status_code,
                422,
            )
            self.assertEqual(
                internal.post("/api/lumi/message", headers=internal_headers, json={"message": "oi"}).status_code,
                200,
            )
            provider.assert_called_once()
        finally:
            internal.close()
            external.close()

    def test_capabilities_requires_a_real_session(self):
        os.environ.update({"LUMI_PUBLIC_ENABLED": "true", "LUMI_ROLLOUT_MODE": "all"})
        self.assertEqual(self.client.get("/api/lumi/capabilities").status_code, 401)


if __name__ == "__main__":
    unittest.main()
