import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core import llm_service


class LlmServiceTests(unittest.TestCase):
    def test_call_llm_uses_solar_pro3(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="response"))]
        )

        with (
            patch.dict(os.environ, {"UPSTAGE_API_KEY": "test-key"}),
            patch.object(
                llm_service.client.chat.completions,
                "create",
                return_value=response,
            ) as create,
        ):
            self.assertEqual("response", llm_service.call_llm("prompt"))

        create.assert_called_once_with(
            model="solar-pro3",
            messages=[{"role": "user", "content": "prompt"}],
            temperature=0.3,
        )


if __name__ == "__main__":
    unittest.main()
