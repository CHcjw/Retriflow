import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowModelHealthTests(unittest.TestCase):
    def tearDown(self) -> None:
        keys = [
            "RETRIFLOW_CHAT_PROVIDER",
            "RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD",
            "RETRIFLOW_MODEL_HEALTH_OPEN_COOLDOWN_SECONDS",
            "BAILIAN_API_KEY",
            "SILICONFLOW_API_KEY",
        ]
        for key in keys:
            os.environ.pop(key, None)

        from core.config import get_settings
        from infra.llm.health import get_model_health_service

        get_settings.cache_clear()
        get_model_health_service().reset(reset_config=True)

    def test_auto_provider_resolution_skips_open_circuit_provider(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "auto"
        os.environ["RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD"] = "1"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        service.model_health.record_failure(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            error="timeout",
        )

        provider = service._resolve_provider(capability="chat")

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "siliconflow")

    def test_requested_provider_degrades_to_fallback_when_circuit_is_open(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "bailian"
        os.environ["RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD"] = "1"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        service.model_health.record_failure(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            error="timeout",
        )

        provider = service._resolve_provider(capability="chat")

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "siliconflow")

    def test_half_open_probe_success_restores_provider_health(self) -> None:
        from infra.llm.health import ModelHealthService

        now = 1000.0

        def clock() -> float:
            return now

        service = ModelHealthService(
            failure_threshold=1,
            open_cooldown_seconds=5,
            clock=clock,
        )
        service.record_failure(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            error="timeout",
        )

        snapshot = service.get_snapshot(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
        )
        self.assertEqual(snapshot.state, "open")
        self.assertFalse(
            service.is_call_allowed(
                capability="chat",
                provider_name="bailian",
                model="qwen3-max",
            )
        )

        now = 1006.0
        self.assertTrue(
            service.is_call_allowed(
                capability="chat",
                provider_name="bailian",
                model="qwen3-max",
            )
        )
        snapshot = service.get_snapshot(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
        )
        self.assertEqual(snapshot.state, "half_open")
        self.assertTrue(snapshot.half_open_in_flight)

        self.assertFalse(
            service.is_call_allowed(
                capability="chat",
                provider_name="bailian",
                model="qwen3-max",
            )
        )

        service.record_success(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            duration_ms=42,
        )
        snapshot = service.get_snapshot(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
        )

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.failure_count, 0)
        self.assertEqual(snapshot.last_success_duration_ms, 42)

    def test_probe_model_health_records_success_snapshot(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "bailian"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()

        def fake_post_json(self, provider, payload, path, capability="chat"):
            self.model_health.record_success(
                capability=capability,
                provider_name=provider.name,
                model=payload["model"],
                duration_ms=12,
            )
            return {"choices": [{"message": {"content": "ok"}}]}

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            snapshot = service.probe_model_health(capability="chat", provider_name="bailian")

        self.assertEqual(snapshot.provider_name, "bailian")
        self.assertEqual(snapshot.model, "qwen3-max")
        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.success_count, 1)

    def test_generate_answer_falls_back_when_first_provider_call_fails(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "auto"
        os.environ["RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD"] = "1"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        attempted: list[str] = []

        def fake_post_json(self, provider, payload, path, capability="chat"):
            attempted.append(provider.name)
            if provider.name == "bailian":
                self.model_health.record_failure(
                    capability=capability,
                    provider_name=provider.name,
                    model=payload["model"],
                    error="timeout",
                )
                raise RuntimeError("timeout")
            self.model_health.record_success(
                capability=capability,
                provider_name=provider.name,
                model=payload["model"],
                duration_ms=18,
            )
            return {"choices": [{"message": {"content": "fallback answer"}}]}

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            answer = service.generate_answer(question="hello", sources=[])

        self.assertEqual(answer, "fallback answer")
        self.assertEqual(attempted[:2], ["bailian", "siliconflow"])

        bailian_snapshot = service.model_health.get_snapshot(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
        )
        self.assertEqual(bailian_snapshot.state, "open")

    def test_stream_answer_falls_back_when_first_provider_fails_before_first_chunk(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "auto"
        os.environ["RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD"] = "1"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        attempted: list[str] = []

        def fake_stream_provider_answer(self, *, provider, payload):
            attempted.append(provider.name)
            if provider.name == "bailian":
                self.model_health.record_failure(
                    capability="chat",
                    provider_name=provider.name,
                    model=payload["model"],
                    error="connect timeout",
                )
                raise RuntimeError("connect timeout")

            self.model_health.record_first_packet(
                capability="chat",
                provider_name=provider.name,
                model=payload["model"],
                first_packet_ms=8,
            )
            yield "fallback "
            yield "answer"
            self.model_health.record_success(
                capability="chat",
                provider_name=provider.name,
                model=payload["model"],
                duration_ms=21,
            )

        with patch(
            "infra.llm.service.RetriFlowLLMService._stream_provider_answer",
            new=fake_stream_provider_answer,
        ):
            chunks = list(service.stream_answer(question="hello", sources=[]))

        self.assertEqual(chunks, ["fallback ", "answer"])
        self.assertEqual(attempted[:2], ["bailian", "siliconflow"])

        bailian_snapshot = service.model_health.get_snapshot(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
        )
        self.assertEqual(bailian_snapshot.state, "open")

        siliconflow_snapshot = service.model_health.get_snapshot(
            capability="chat",
            provider_name="siliconflow",
            model="qwen3-max",
        )
        self.assertEqual(siliconflow_snapshot.state, "healthy")
        self.assertEqual(siliconflow_snapshot.success_count, 1)
        self.assertEqual(siliconflow_snapshot.last_first_packet_ms, 8)

    def test_stream_answer_does_not_fallback_after_first_chunk_is_sent(self) -> None:
        os.environ["RETRIFLOW_CHAT_PROVIDER"] = "auto"
        os.environ["RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD"] = "1"
        os.environ["BAILIAN_API_KEY"] = "bailian-key"
        os.environ["SILICONFLOW_API_KEY"] = "siliconflow-key"

        from core.config import get_settings
        from infra.llm import RetriFlowLLMService

        get_settings.cache_clear()
        service = RetriFlowLLMService()
        attempted: list[str] = []
        received: list[str] = []

        def fake_stream_provider_answer(self, *, provider, payload):
            attempted.append(provider.name)
            self.model_health.record_first_packet(
                capability="chat",
                provider_name=provider.name,
                model=payload["model"],
                first_packet_ms=9,
            )
            yield "first"
            self.model_health.record_failure(
                capability="chat",
                provider_name=provider.name,
                model=payload["model"],
                error="mid-stream disconnect",
            )
            raise RuntimeError("mid-stream disconnect")

        with patch(
            "infra.llm.service.RetriFlowLLMService._stream_provider_answer",
            new=fake_stream_provider_answer,
        ):
            stream = service.stream_answer(question="hello", sources=[])
            with self.assertRaises(RuntimeError):
                for chunk in stream:
                    received.append(chunk)

        self.assertEqual(received, ["first"])
        self.assertEqual(attempted, ["bailian"])


if __name__ == "__main__":
    unittest.main()
