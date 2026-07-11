import os
import unittest
from unittest.mock import patch

from app.main import get_cors_origins, liveness_check, readiness_check


class AppConfigTests(unittest.TestCase):
    def test_cors_origins_are_read_from_environment(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://shop.example.com/, https://admin.example.com"}):
            self.assertEqual(
                ["https://shop.example.com", "https://admin.example.com"],
                get_cors_origins(),
            )

    def test_health_checks_succeed_with_writable_data_directory(self):
        with self.subTest("liveness"):
            self.assertEqual({"status": "ok"}, liveness_check())

        with patch.dict(os.environ, {"APP_DB_PATH": "/tmp/shopbuddy-test/shopbuddy.db", "CHROMA_DB_PATH": "/tmp/shopbuddy-test/chroma"}):
            self.assertEqual({"status": "ready"}, readiness_check())


if __name__ == "__main__":
    unittest.main()
