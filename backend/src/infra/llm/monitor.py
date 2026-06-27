from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from core.config import Settings, get_settings
from infra.llm.service import RetriFlowLLMService


@dataclass(frozen=True)
class ModelHealthProbeTarget:
    capability: str
    provider_name: str | None = None
    model: str | None = None


class ModelHealthProbeScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        if not self.settings.model_health_probe_enabled and not self.settings.model_health_startup_probe_enabled:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="retriflow-model-health-probe")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        self._stop_event = None

    async def _run(self) -> None:
        if self.settings.model_health_startup_probe_enabled:
            await self.probe_once()

        if not self.settings.model_health_probe_enabled:
            return

        interval = max(30, int(self.settings.model_health_probe_interval_seconds))
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                await self.probe_once()

    async def probe_once(self) -> None:
        targets = self._probe_targets()
        if not targets:
            return
        await asyncio.to_thread(self._probe_targets_sync, targets)

    def _probe_targets_sync(self, targets: list[ModelHealthProbeTarget]) -> None:
        service = RetriFlowLLMService()
        for target in targets:
            try:
                service.probe_model_health(
                    capability=target.capability,
                    provider_name=target.provider_name,
                    model=target.model,
                )
            except Exception as exc:
                print(
                    "[RetriFlow] model health probe failed"
                    f" | capability={target.capability}"
                    f" | provider={target.provider_name or 'auto'}"
                    f" | error={exc}"
                )

    def _probe_targets(self) -> list[ModelHealthProbeTarget]:
        capabilities = [
            capability.strip()
            for capability in self.settings.model_health_probe_capabilities.split(",")
            if capability.strip()
        ]
        return [ModelHealthProbeTarget(capability=capability) for capability in capabilities]


_MODEL_HEALTH_PROBE_SCHEDULER: ModelHealthProbeScheduler | None = None


def get_model_health_probe_scheduler() -> ModelHealthProbeScheduler:
    global _MODEL_HEALTH_PROBE_SCHEDULER
    if _MODEL_HEALTH_PROBE_SCHEDULER is None:
        _MODEL_HEALTH_PROBE_SCHEDULER = ModelHealthProbeScheduler()
    return _MODEL_HEALTH_PROBE_SCHEDULER


def reset_model_health_probe_scheduler() -> None:
    global _MODEL_HEALTH_PROBE_SCHEDULER
    _MODEL_HEALTH_PROBE_SCHEDULER = None
