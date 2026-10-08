from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from unittest.mock import patch

from database.connection import get_connection
from repositories.periodic_summary_job_repo import list_latest_job_runs
from services.notification_maintenance_service import NotificationMaintenanceRunner
from services.notification_service import notification_service
from services.notification_types import NotificationType
from tests.db_support import remove_test_database, reset_test_database


REFERENCE = date(2026, 10, 8)
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
ENVIRONMENT = {
    "NOTIFICATION_MAINTENANCE_ENABLED": "true",
    "NOTIFICATION_READ_RETENTION_DAYS": "30",
    "NOTIFICATION_JOB_RETENTION_DAYS": "30",
    "NOTIFICATION_MAINTENANCE_BATCH_SIZE": "1",
}


class NotificationMaintenanceTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        try:
            connection.execute(
                "INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,?,?,?)",
                ("Maintenance", "maintenance@example.invalid", "hash"),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        remove_test_database()

    @staticmethod
    def _runner() -> NotificationMaintenanceRunner:
        return NotificationMaintenanceRunner(utc_now=lambda: NOW, sleeper=lambda _seconds: None)

    def _notification(self, key: str) -> dict:
        delivery = notification_service.deliver(
            1,
            NotificationType.SYSTEM,
            f"Title {key}",
            f"Message {key}",
            metadata={"route": "/dashboard", "source_type": "test", "source_id": key},
            dedupe_key=key,
        )
        assert delivery.notification is not None
        return delivery.notification

    def test_cleanup_deletes_only_old_read_data_and_preserves_domain_state(self):
        expired = self._notification("expired")
        unread = self._notification("unread")
        recent = self._notification("recent")
        notification_service.mark_read(1, expired["id"])
        notification_service.mark_read(1, recent["id"])
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE notifications SET criada_em='2026-08-01 00:00:00' WHERE id IN (?,?,?)",
                (expired["id"], unread["id"], recent["id"]),
            )
            connection.execute(
                "UPDATE notifications SET lida_em='2026-08-02 00:00:00' WHERE id=?",
                (expired["id"],),
            )
            connection.execute(
                "INSERT INTO notification_preferences (usuario_id,preference_key,enabled) "
                "VALUES (1,'card_limit',0)"
            )
            connection.execute(
                "INSERT INTO notification_preference_suppressions "
                "(usuario_id,preference_key,dedupe_key) VALUES (1,'card_limit','suppressed:key')"
            )
            connection.execute(
                "INSERT INTO financial_alert_states "
                "(usuario_id,source_kind,source_id,period_key,highest_milestone) "
                "VALUES (1,'budget',7,'2026-10',80)"
            )
            connection.execute(
                "INSERT INTO categorias (id,nome,usuario_id) VALUES (7,'Moradia',1)"
            )
            connection.execute(
                "INSERT INTO budgets (id,usuario_id,categoria_id,periodo,limite) "
                "VALUES (7,1,7,'2026-10-01',1500)"
            )
            connection.execute(
                "INSERT INTO goals (id,usuario_id,nome,valor_alvo) "
                "VALUES (9,1,'Reserva',5000)"
            )
            for period, finished in (("2026-07-01", "2026-07-02 00:00:00"), ("2026-10-01", "2026-10-02 00:00:00")):
                connection.execute(
                    "INSERT INTO periodic_summary_job_runs "
                    "(job_type,period_start,period_end,reference_date,status,attempt,started_at,finished_at) "
                    "VALUES ('weekly',?,?,?,?,1,?,?)",
                    (period, period, period, "success", finished, finished),
                )
            connection.commit()
        finally:
            connection.close()

        with patch.dict(os.environ, ENVIRONMENT, clear=False):
            result = self._runner().run(reference=REFERENCE)
        self.assertEqual(result.status, "success")
        self.assertEqual((result.counters.success, result.counters.skipped), (1, 1))

        connection = get_connection()
        try:
            visible_keys = {row[0] for row in connection.execute(
                "SELECT chave_dedupe FROM notifications ORDER BY chave_dedupe"
            ).fetchall()}
            self.assertEqual(visible_keys, {"recent", "unread"})
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM notification_dedupe_ledger"
            ).fetchone()[0], 3)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM notification_preferences"
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM notification_preference_suppressions"
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM financial_alert_states"
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT limite FROM budgets WHERE id=7").fetchone()[0], 1500)
            self.assertEqual(connection.execute("SELECT valor_alvo FROM goals WHERE id=9").fetchone()[0], 5000)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM periodic_summary_job_runs WHERE job_type='weekly'"
            ).fetchone()[0], 1)
        finally:
            connection.close()

        replay = notification_service.deliver(
            1,
            NotificationType.SYSTEM,
            "Replay",
            "Must stay deduplicated",
            dedupe_key="expired",
        )
        self.assertTrue(replay.deduplicated)
        self.assertIsNone(replay.notification)
        self.assertEqual(notification_service.unread_count(1), 1)

    def test_dry_run_counts_without_deleting_or_tracking(self):
        expired = self._notification("dry-run")
        notification_service.mark_read(1, expired["id"])
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE notifications SET criada_em='2026-08-01 00:00:00', "
                "lida_em='2026-08-02 00:00:00' WHERE id=?",
                (expired["id"],),
            )
            connection.commit()
        finally:
            connection.close()
        result = self._runner().run(
            reference=REFERENCE,
            read_days=30,
            job_days=30,
            batch_size=1,
            dry_run=True,
        )
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.counters.success, 1)
        connection = get_connection()
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM periodic_summary_job_runs").fetchone()[0], 0)
        finally:
            connection.close()

    def test_policy_is_explicit_and_concurrent_runs_have_one_tracking_row(self):
        with patch.dict(os.environ, {}, clear=True):
            disabled = self._runner().run(reference=REFERENCE)
        self.assertEqual((disabled.status, disabled.reason), ("skipped", "feature_flag_off"))
        with patch.dict(os.environ, {"NOTIFICATION_MAINTENANCE_ENABLED": "true"}, clear=True):
            with self.assertRaises(RuntimeError):
                self._runner().run(reference=REFERENCE)
        with patch.dict(os.environ, ENVIRONMENT, clear=False):
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(lambda _index: self._runner().run(reference=REFERENCE), range(8)))
        self.assertEqual(sum(result.reason == "completed" for result in results), 1)
        self.assertTrue(all(result.status in {"success", "skipped"} for result in results))
        latest = list_latest_job_runs()
        self.assertNotIn("lease_token", latest[0])
        connection = get_connection()
        try:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM periodic_summary_job_runs WHERE job_type='cleanup'"
            ).fetchone()[0], 1)
        finally:
            connection.close()

    def test_expired_lease_is_recovered_and_transient_failure_is_retried(self):
        connection = get_connection()
        try:
            connection.execute(
                "INSERT INTO periodic_summary_job_runs "
                "(job_type,period_start,period_end,reference_date,status,lease_token,"
                "lease_expires_at,attempt,started_at) "
                "VALUES ('cleanup',?,?,?,?,?,?,1,?)",
                (
                    REFERENCE.isoformat(),
                    REFERENCE.isoformat(),
                    REFERENCE.isoformat(),
                    "running",
                    "stale-token",
                    "2026-10-08 11:00:00",
                    "2026-10-08 10:00:00",
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with (
            patch.dict(os.environ, ENVIRONMENT, clear=False),
            patch(
                "services.notification_maintenance_service.delete_expired_read_notifications",
                side_effect=[ConnectionError("transient"), 0],
            ),
        ):
            result = self._runner().run(reference=REFERENCE)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.attempt, 2)
        self.assertEqual(result.counters.retries, 1)


if __name__ == "__main__":
    unittest.main()
