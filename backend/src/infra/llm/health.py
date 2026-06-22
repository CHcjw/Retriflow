from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable


ModelHealthState = str


@dataclass
class ModelHealthSnapshot:
    capability: str
    provider_name: str
    model: str
    state: ModelHealthState = "healthy"
    failure_count: int = 0
    success_count: int = 0
    opened_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str = ""
    last_success_duration_ms: int | None = None
    last_first_packet_ms: int | None = None
    half_open_in_flight: bool = False


class ModelHealthService:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        open_cooldown_seconds: int = 60,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.open_cooldown_seconds = max(0, open_cooldown_seconds)
        self._clock = clock or time.time
        self._snapshots: dict[tuple[str, str, str], ModelHealthSnapshot] = {}

    def is_call_allowed(self, *, capability: str, provider_name: str, model: str) -> bool:
        snapshot = self.get_snapshot(
            capability=capability,
            provider_name=provider_name,
            model=model,
        )
        if snapshot.state == "half_open":
            if snapshot.half_open_in_flight:
                return False
            snapshot.half_open_in_flight = True
            self._persist_snapshot(snapshot)
            return True
        if snapshot.state != "open":
            return True
        if snapshot.opened_at is None:
            return False
        if self._clock() - snapshot.opened_at < self.open_cooldown_seconds:
            return False
        snapshot.state = "half_open"
        snapshot.half_open_in_flight = True
        self._persist_snapshot(snapshot)
        return True

    def record_success(
        self,
        *,
        capability: str,
        provider_name: str,
        model: str,
        duration_ms: int | None = None,
    ) -> None:
        snapshot = self.get_snapshot(
            capability=capability,
            provider_name=provider_name,
            model=model,
        )
        snapshot.state = "healthy"
        snapshot.failure_count = 0
        snapshot.success_count += 1
        snapshot.opened_at = None
        snapshot.half_open_in_flight = False
        snapshot.last_error = ""
        snapshot.last_success_at = self._clock()
        snapshot.last_success_duration_ms = duration_ms
        self._persist_snapshot(snapshot)

    def record_failure(
        self,
        *,
        capability: str,
        provider_name: str,
        model: str,
        error: str,
    ) -> None:
        snapshot = self.get_snapshot(
            capability=capability,
            provider_name=provider_name,
            model=model,
        )
        snapshot.failure_count += 1
        snapshot.last_failure_at = self._clock()
        snapshot.last_error = error
        if snapshot.state == "half_open" or snapshot.failure_count >= self.failure_threshold:
            snapshot.state = "open"
            snapshot.opened_at = snapshot.last_failure_at
            snapshot.half_open_in_flight = False
        self._persist_snapshot(snapshot)

    def record_first_packet(
        self,
        *,
        capability: str,
        provider_name: str,
        model: str,
        first_packet_ms: int,
    ) -> None:
        snapshot = self.get_snapshot(
            capability=capability,
            provider_name=provider_name,
            model=model,
        )
        snapshot.last_first_packet_ms = first_packet_ms
        self._persist_snapshot(snapshot)

    def get_snapshot(self, *, capability: str, provider_name: str, model: str) -> ModelHealthSnapshot:
        key = self._key(capability=capability, provider_name=provider_name, model=model)
        if key not in self._snapshots:
            self._snapshots[key] = ModelHealthSnapshot(
                capability=capability,
                provider_name=provider_name,
                model=model,
            )
        return self._snapshots[key]

    def list_snapshots(self) -> list[ModelHealthSnapshot]:
        return sorted(
            self._snapshots.values(),
            key=lambda item: (item.capability, item.provider_name, item.model),
        )

    def hydrate_from_persistence(self) -> None:
        try:
            from core.state import get_connection

            with get_connection() as connection:
                rows = connection.execute(
                    """
                    select capability, provider_name, model, state, failure_count, success_count,
                           opened_at, last_success_at, last_failure_at, last_error,
                           last_success_duration_ms, last_first_packet_ms, half_open_in_flight
                    from model_health
                    order by capability, provider_name, model
                    """
                ).fetchall()
        except Exception:
            return

        for row in rows:
            snapshot = ModelHealthSnapshot(
                capability=str(row["capability"]),
                provider_name=str(row["provider_name"]),
                model=str(row["model"]),
                state=str(row["state"] or "healthy"),
                failure_count=int(row["failure_count"] or 0),
                success_count=int(row["success_count"] or 0),
                opened_at=self._optional_float(row["opened_at"]),
                last_success_at=self._optional_float(row["last_success_at"]),
                last_failure_at=self._optional_float(row["last_failure_at"]),
                last_error=str(row["last_error"] or ""),
                last_success_duration_ms=self._optional_int(row["last_success_duration_ms"]),
                last_first_packet_ms=self._optional_int(row["last_first_packet_ms"]),
                half_open_in_flight=bool(row["half_open_in_flight"]),
            )
            self._snapshots[
                self._key(
                    capability=snapshot.capability,
                    provider_name=snapshot.provider_name,
                    model=snapshot.model,
                )
            ] = snapshot

    def reset(self, *, reset_config: bool = False) -> None:
        self._snapshots.clear()
        if reset_config:
            self.failure_threshold = 3
            self.open_cooldown_seconds = 60

    def _persist_snapshot(self, snapshot: ModelHealthSnapshot) -> None:
        try:
            from core.state import get_connection

            with get_connection() as connection:
                connection.execute(
                    """
                    insert into model_health (
                        capability, provider_name, model, state, failure_count, success_count,
                        opened_at, last_success_at, last_failure_at, last_error,
                        last_success_duration_ms, last_first_packet_ms, half_open_in_flight
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict (capability, provider_name, model) do update set
                        state = excluded.state,
                        failure_count = excluded.failure_count,
                        success_count = excluded.success_count,
                        opened_at = excluded.opened_at,
                        last_success_at = excluded.last_success_at,
                        last_failure_at = excluded.last_failure_at,
                        last_error = excluded.last_error,
                        last_success_duration_ms = excluded.last_success_duration_ms,
                        last_first_packet_ms = excluded.last_first_packet_ms,
                        half_open_in_flight = excluded.half_open_in_flight,
                        updated_at = current_timestamp
                    """,
                    (
                        snapshot.capability,
                        snapshot.provider_name,
                        snapshot.model,
                        snapshot.state,
                        snapshot.failure_count,
                        snapshot.success_count,
                        snapshot.opened_at,
                        snapshot.last_success_at,
                        snapshot.last_failure_at,
                        snapshot.last_error,
                        snapshot.last_success_duration_ms,
                        snapshot.last_first_packet_ms,
                        1 if snapshot.half_open_in_flight else 0,
                    ),
                )
                connection.commit()
        except Exception:
            return

    @staticmethod
    def _key(*, capability: str, provider_name: str, model: str) -> tuple[str, str, str]:
        return (
            capability.strip().lower(),
            provider_name.strip().lower(),
            model.strip(),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        return int(value)


_MODEL_HEALTH_SERVICE = ModelHealthService()


def get_model_health_service() -> ModelHealthService:
    return _MODEL_HEALTH_SERVICE
