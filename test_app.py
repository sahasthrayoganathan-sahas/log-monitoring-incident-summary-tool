import unittest

from app import parse_log_line, normalize_error, get_time_window


class TestLogMonitoring(unittest.TestCase):

    def test_parse_log_line(self):
        line = (
            "2026-09-29 10:00:01 | ERROR | "
            "PaymentService | Database connection failed"
        )

        result = parse_log_line(line)

        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "PaymentService")
        self.assertEqual(
            result["message"],
            "Database connection failed"
        )

    def test_normalize_error(self):
        result = normalize_error(
            "Database connection failed"
        )

        self.assertEqual(
            result,
            "database_connection_failed"
        )

    def test_time_window(self):
        result = get_time_window(
            "2026-09-29 10:07:30",
            5
        )

        self.assertEqual(
            result,
            "2026-09-29 10:05:00"
        )


if __name__ == "__main__":
    unittest.main()