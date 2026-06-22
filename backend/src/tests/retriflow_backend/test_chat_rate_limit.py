import sys
import threading
import time
import unittest
from pathlib import Path
import os
import asyncio
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowChatRateLimitTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [
            "RETRIFLOW_CHAT_QUEUE_ENABLED",
            "RETRIFLOW_CHAT_QUEUE_MAX_CONCURRENT",
            "RETRIFLOW_CHAT_QUEUE_MAX_WAIT_SECONDS",
            "RETRIFLOW_CHAT_QUEUE_BACKEND",
            "RETRIFLOW_CHAT_QUEUE_REDIS_URL",
            "RETRIFLOW_CHAT_QUEUE_REDIS_KEY_PREFIX",
        ]:
            os.environ.pop(key, None)

        from core.config import get_settings
        from modules.chat.rate_limit import reset_chat_queue_limiter

        get_settings.cache_clear()
        reset_chat_queue_limiter()

    @staticmethod
    def _create_session(session_id: str, user_id: str = "user-demo") -> None:
        from core.state import get_connection
        from core.state import initialize_database

        initialize_database()
        with get_connection() as connection:
            row = connection.execute(
                """
                select id
                from sessions
                where id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    insert into sessions (id, title, message_count, owner_id)
                    values (?, ?, ?, ?)
                    """,
                    (session_id, "Queue reject test", 0, user_id),
                )
                connection.commit()

    @staticmethod
    def _list_session_messages(session_id: str) -> list[tuple[str, str]]:
        from core.state import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                """
                select role, content
                from conversation_messages
                where session_id = ?
                order by id
                """,
                (session_id,),
            ).fetchall()
        return [(row["role"], row["content"]) for row in rows]

    def test_limiter_rejects_when_queue_wait_times_out(self) -> None:
        from modules.chat.rate_limit import RetriFlowFairQueueLimiter

        limiter = RetriFlowFairQueueLimiter(max_concurrent=1)
        first = limiter.acquire(max_wait_seconds=0.1)
        self.assertTrue(first.acquired)

        second = limiter.acquire(max_wait_seconds=0.01)

        self.assertFalse(second.acquired)
        self.assertEqual(second.reason, "timeout")
        first.release()

    def test_limiter_grants_waiting_ticket_after_release_in_fifo_order(self) -> None:
        from modules.chat.rate_limit import RetriFlowFairQueueLimiter

        limiter = RetriFlowFairQueueLimiter(max_concurrent=1)
        first = limiter.acquire(max_wait_seconds=0.1)
        self.assertTrue(first.acquired)

        results: list[str] = []

        def wait_for_second() -> None:
            ticket = limiter.acquire(max_wait_seconds=1)
            if ticket.acquired:
                results.append(ticket.request_id)
                ticket.release()

        worker = threading.Thread(target=wait_for_second)
        worker.start()
        time.sleep(0.05)

        self.assertEqual(results, [])
        first.release()
        worker.join(timeout=1)

        self.assertEqual(len(results), 1)

    def test_limiter_snapshot_reports_active_queue_and_available_permits(self) -> None:
        from modules.chat.rate_limit import RetriFlowFairQueueLimiter

        limiter = RetriFlowFairQueueLimiter(max_concurrent=2)
        first = limiter.acquire(max_wait_seconds=0.1)
        self.assertTrue(first.acquired)

        snapshot = limiter.snapshot()

        self.assertEqual(snapshot["backend"], "memory")
        self.assertEqual(snapshot["max_concurrent"], 2)
        self.assertEqual(snapshot["active_count"], 1)
        self.assertEqual(snapshot["queued_count"], 0)
        self.assertEqual(snapshot["available_permits"], 1)
        first.release()

    def test_limiter_cleans_waiting_ticket_when_cancelled(self) -> None:
        from modules.chat.rate_limit import RetriFlowFairQueueLimiter

        limiter = RetriFlowFairQueueLimiter(max_concurrent=1)
        first = limiter.acquire(max_wait_seconds=0.1)
        self.assertTrue(first.acquired)

        cancel_event = threading.Event()
        results: list[tuple[bool, str]] = []

        def wait_for_second() -> None:
            ticket = limiter.acquire(max_wait_seconds=1, cancel_event=cancel_event)
            results.append((ticket.acquired, ticket.reason))

        worker = threading.Thread(target=wait_for_second)
        worker.start()
        time.sleep(0.05)
        cancel_event.set()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [(False, "cancelled")])

        first.release()
        third = limiter.acquire(max_wait_seconds=0.1)
        self.assertTrue(third.acquired)
        third.release()

    def test_streaming_service_emits_reject_when_queue_times_out(self) -> None:
        os.environ["RETRIFLOW_CHAT_QUEUE_ENABLED"] = "true"
        os.environ["RETRIFLOW_CHAT_QUEUE_BACKEND"] = "memory"
        os.environ["RETRIFLOW_CHAT_QUEUE_MAX_CONCURRENT"] = "1"
        os.environ["RETRIFLOW_CHAT_QUEUE_MAX_WAIT_SECONDS"] = "0"

        from core.config import get_settings
        from modules.chat.rate_limit import get_chat_queue_limiter
        from modules.chat.streaming import RetriFlowStreamingService
        from schemas.chat import ChatMessageRequest

        get_settings.cache_clear()
        session_id = f"session-queue-reject-{uuid.uuid4().hex}"
        self._create_session(session_id)
        held = get_chat_queue_limiter().acquire(max_wait_seconds=0.1)
        self.assertTrue(held.acquired)

        async def collect_events() -> list[str]:
            stream = RetriFlowStreamingService().build_event_stream(
                ChatMessageRequest(session_id=session_id, message="hello"),
                user_id="user-demo",
            )
            return [event async for event in stream]

        try:
            events = asyncio.run(collect_events())
        finally:
            held.release()

        payload = "".join(events)
        self.assertIn("event: queue", payload)
        self.assertIn('"backend": "memory"', payload)
        self.assertIn('"active_count": 1', payload)
        self.assertIn('"available_permits": 0', payload)
        self.assertIn("event: reject", payload)
        self.assertIn("event: final", payload)
        self.assertIn("event: done", payload)
        self.assertIn('"status": "rejected"', payload)
        self.assertEqual(
            self._list_session_messages(session_id)[-2:],
            [("user", "hello"), ("assistant", "system busy, please retry later")],
        )

    def test_redis_limiter_uses_queue_and_permit_semantics(self) -> None:
        import redis

        from modules.chat.rate_limit import RetriFlowRedisQueueLimiter

        redis_url = os.getenv("RETRIFLOW_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        key_prefix = "retriflow:test:chatqueue"
        for key in client.scan_iter(f"{key_prefix}:*"):
            client.delete(key)

        limiter = RetriFlowRedisQueueLimiter(
            redis_url=redis_url,
            key_prefix=key_prefix,
            max_concurrent=1,
            lease_seconds=5,
            poll_interval_ms=20,
        )
        first = limiter.acquire(max_wait_seconds=0.2)
        self.assertTrue(first.acquired)

        second = limiter.acquire(max_wait_seconds=0.01)
        self.assertFalse(second.acquired)
        self.assertEqual(second.reason, "timeout")
        snapshot = limiter.snapshot()
        self.assertEqual(snapshot["backend"], "redis")
        self.assertEqual(snapshot["max_concurrent"], 1)
        self.assertEqual(snapshot["active_count"], 1)
        self.assertEqual(snapshot["available_permits"], 0)

        results: list[str] = []

        def wait_for_third() -> None:
            ticket = limiter.acquire(max_wait_seconds=1)
            if ticket.acquired:
                results.append(ticket.request_id)
                ticket.release()

        worker = threading.Thread(target=wait_for_third)
        worker.start()
        time.sleep(0.05)
        self.assertEqual(results, [])
        first.release()
        worker.join(timeout=1)

        self.assertEqual(len(results), 1)

    def test_redis_limiter_cleans_waiting_ticket_when_cancelled(self) -> None:
        import redis

        from modules.chat.rate_limit import RetriFlowRedisQueueLimiter

        redis_url = os.getenv("RETRIFLOW_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        key_prefix = "retriflow:test:chatqueue:cancel"
        for key in client.scan_iter(f"{key_prefix}:*"):
            client.delete(key)

        limiter = RetriFlowRedisQueueLimiter(
            redis_url=redis_url,
            key_prefix=key_prefix,
            max_concurrent=1,
            lease_seconds=5,
            poll_interval_ms=5000,
        )
        first = limiter.acquire(max_wait_seconds=0.2)
        self.assertTrue(first.acquired)

        cancel_event = threading.Event()
        results: list[tuple[bool, str]] = []

        def wait_for_second() -> None:
            ticket = limiter.acquire(max_wait_seconds=2, cancel_event=cancel_event)
            results.append((ticket.acquired, ticket.reason))

        worker = threading.Thread(target=wait_for_second)
        worker.start()
        time.sleep(0.1)
        cancel_event.set()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [(False, "cancelled")])
        self.assertEqual(client.zcard(f"{key_prefix}:queue"), 0)

        first.release()
        third = limiter.acquire(max_wait_seconds=0.2)
        self.assertTrue(third.acquired)
        third.release()

    def test_redis_limiter_wakes_waiter_from_release_publish_without_poll_delay(self) -> None:
        import redis

        from modules.chat.rate_limit import RetriFlowRedisQueueLimiter

        redis_url = os.getenv("RETRIFLOW_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        key_prefix = "retriflow:test:chatqueue:notify"
        for key in client.scan_iter(f"{key_prefix}:*"):
            client.delete(key)

        limiter = RetriFlowRedisQueueLimiter(
            redis_url=redis_url,
            key_prefix=key_prefix,
            max_concurrent=1,
            lease_seconds=5,
            poll_interval_ms=5000,
        )
        first = limiter.acquire(max_wait_seconds=0.2)
        self.assertTrue(first.acquired)

        elapsed: list[float] = []
        results: list[bool] = []

        def wait_for_second() -> None:
            started_at = time.perf_counter()
            ticket = limiter.acquire(max_wait_seconds=2)
            elapsed.append(time.perf_counter() - started_at)
            results.append(ticket.acquired)
            ticket.release()

        worker = threading.Thread(target=wait_for_second)
        worker.start()
        time.sleep(0.1)
        first.release()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [True])
        self.assertLess(elapsed[0], 0.8)

    def test_streaming_service_can_reject_through_redis_queue_backend(self) -> None:
        import redis

        redis_url = os.getenv("RETRIFLOW_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        key_prefix = "retriflow:test:streamqueue"
        for key in client.scan_iter(f"{key_prefix}:*"):
            client.delete(key)

        os.environ["RETRIFLOW_CHAT_QUEUE_ENABLED"] = "true"
        os.environ["RETRIFLOW_CHAT_QUEUE_BACKEND"] = "redis"
        os.environ["RETRIFLOW_CHAT_QUEUE_REDIS_URL"] = redis_url
        os.environ["RETRIFLOW_CHAT_QUEUE_REDIS_KEY_PREFIX"] = key_prefix
        os.environ["RETRIFLOW_CHAT_QUEUE_MAX_CONCURRENT"] = "1"
        os.environ["RETRIFLOW_CHAT_QUEUE_MAX_WAIT_SECONDS"] = "0"

        from core.config import get_settings
        from modules.chat.rate_limit import get_chat_queue_limiter
        from modules.chat.streaming import RetriFlowStreamingService
        from schemas.chat import ChatMessageRequest

        get_settings.cache_clear()
        session_id = f"session-queue-redis-reject-{uuid.uuid4().hex}"
        self._create_session(session_id)
        held = get_chat_queue_limiter().acquire(max_wait_seconds=0.1)
        self.assertTrue(held.acquired)

        async def collect_events() -> list[str]:
            stream = RetriFlowStreamingService().build_event_stream(
                ChatMessageRequest(session_id=session_id, message="hello"),
                user_id="user-demo",
            )
            return [event async for event in stream]

        try:
            events = asyncio.run(collect_events())
        finally:
            held.release()

        payload = "".join(events)
        self.assertIn("event: queue", payload)
        self.assertIn('"backend": "redis"', payload)
        self.assertIn('"active_count": 1', payload)
        self.assertIn("event: reject", payload)
        self.assertIn("event: final", payload)
        self.assertIn("event: done", payload)


if __name__ == "__main__":
    unittest.main()
