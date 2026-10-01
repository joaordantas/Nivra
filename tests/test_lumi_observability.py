import unittest
import logging

from services.lumi_observability import log_lumi_event


class LumiObservabilityTests(unittest.TestCase):
    def test_logger_emits_info_without_inheriting_a_warning_threshold(self):
        logger = logging.getLogger("nivra.lumi")
        self.assertEqual(logger.level, logging.INFO)

    def test_structured_event_contains_only_operational_dimensions(self):
        logger = logging.getLogger("nivra.lumi")
        was_disabled = logger.disabled
        logger.disabled = False
        try:
            with self.assertLogs("nivra.lumi", level="INFO") as captured:
                log_lumi_event(
                    "request_completed",
                    outcome="error",
                    duration_ms=321,
                    error_code="LumiProviderTimeoutError",
                    provider="fake",
                    tool_calls=0,
                    prompt="não deve aparecer",
                    user_id=123,
                )
        finally:
            logger.disabled = was_disabled
        record = captured.output[0]
        self.assertIn('"event":"request_completed"', record)
        self.assertIn('"duration_ms":321', record)
        for forbidden in ("prompt", "cookie", "session", "api_key", "password", "connection_string"):
            self.assertNotIn(forbidden, record.lower())
        self.assertNotIn("user_id", record)
        self.assertNotIn("não deve aparecer", record)


if __name__ == "__main__":
    unittest.main()
