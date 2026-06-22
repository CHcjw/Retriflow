import os
import re
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowRagTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"

        from core.config import get_settings
        from core.state import initialize_database

        get_settings.cache_clear()
        initialize_database()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)

        from core.config import get_settings

        get_settings.cache_clear()
        self.temp_dir.cleanup()

    def test_trace_service_persists_root_and_nested_node_with_parent_stack(self) -> None:
        from modules.rag.trace import RetriFlowTraceService

        service = RetriFlowTraceService()
        with service.start_root(session_id="session-trace", task_id="task-trace", name="chat") as root:
            with service.span(
                name="retrieve",
                node_type="RETRIEVAL",
                input_summary="question",
                metadata={"top_k": 5},
            ) as child:
                child.finish_success(output_summary="5 chunks")
            root.finish_success(output_summary="done")

        nodes = service.list_nodes("session-trace")

        self.assertEqual(len(nodes), 2)
        root_node = nodes[0]
        child_node = nodes[1]
        self.assertEqual(root_node["name"], "chat")
        self.assertRegex(root_node["id"], re.compile(r"^\d{20}$"))
        self.assertEqual(root_node["node_type"], "ROOT")
        self.assertEqual(root_node["status"], "success")
        self.assertEqual(child_node["parent_id"], root_node["id"])
        self.assertEqual(child_node["name"], "retrieve")
        self.assertEqual(child_node["node_type"], "RETRIEVAL")
        self.assertEqual(child_node["status"], "success")
        self.assertEqual(child_node["input_summary"], "question")
        self.assertEqual(child_node["output_summary"], "5 chunks")
        self.assertEqual(child_node["metadata"]["top_k"], 5)
        self.assertGreaterEqual(child_node["duration_ms"], 0)

    def test_stream_span_detaches_and_finishes_later(self) -> None:
        from modules.rag.trace import RetriFlowTraceService

        service = RetriFlowTraceService()
        with service.start_root(session_id="session-stream-trace", task_id="task-stream", name="chat.stream") as root:
            stream_span = service.begin_stream_span(
                name="generation.answer",
                node_type="GENERATION",
                input_summary="stream=true",
                metadata={"mode": "sse"},
            )
            self.assertEqual(service.current_node_id(), stream_span.id)
            stream_span.detach()
            self.assertEqual(service.current_node_id(), root.id)
            root.finish_success(output_summary="prepared")

        running_nodes = service.list_nodes("session-stream-trace")
        root_node = next(node for node in running_nodes if node["name"] == "chat.stream")
        generation_node = next(node for node in running_nodes if node["name"] == "generation.answer")
        self.assertEqual(generation_node["status"], "running")
        self.assertEqual(generation_node["parent_id"], root_node["id"])

        stream_span.finish_success(output_summary="chunks=2")
        stream_span.finish_error(RuntimeError("late failure should be ignored"))

        nodes = service.list_nodes("session-stream-trace")
        finished_generation = next(node for node in nodes if node["name"] == "generation.answer")
        self.assertEqual(finished_generation["status"], "success")
        self.assertEqual(finished_generation["output_summary"], "chunks=2")
        self.assertEqual(finished_generation["error_message"], "")
        self.assertGreaterEqual(finished_generation["duration_ms"], 0)

    def test_root_span_clears_trace_context_after_exit(self) -> None:
        from modules.rag.trace import RetriFlowTraceService

        service = RetriFlowTraceService()
        self.assertFalse(service.has_active_trace())

        with service.start_root(session_id="session-context", task_id="task-context", name="chat") as root:
            self.assertTrue(service.has_active_trace())
            self.assertEqual(service.current_node_id(), root.id)

        self.assertFalse(service.has_active_trace())
        self.assertEqual(service.current_node_id(), "")

        orphan = service.span(name="orphan", node_type="METHOD")
        self.assertEqual(orphan.id, "")
        with orphan:
            orphan.finish_success(output_summary="ignored")
        names = [node["name"] for node in service.list_nodes("session-context")]
        self.assertEqual(names, ["chat"])


if __name__ == "__main__":
    unittest.main()
