from functools import lru_cache
import json
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "RetriFlow API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_backend: str = "auto"
    database_dsn: str = ""
    database_schema: str = "public"
    db_path: str = "backend/data/retriflow.db"
    seed_demo_content: bool = True
    allow_sqlite_fallback: bool = False
    workflow_adapter: str = "auto"
    vector_store_type: str = "pg"
    pgvector_dsn: str = ""
    pgvector_table: str = "retriflow_chunk_vectors"
    default_chat_model: str = "qwen3-max"
    deep_thinking_model: str = "qwen3-max"
    default_embedding_model: str = "qwen-emb-8b"
    default_rerank_model: str = "Qwen/Qwen3-Reranker-8B"
    retrieval_bm25_top_k: int = 80
    retrieval_vector_top_k: int = 80
    retrieval_rrf_top_k: int = 50
    retrieval_rerank_top_k: int = 10
    retrieval_final_top_k: int = 5
    default_route_model: str = "qwen3-max"
    sample_knowledge_dir: str = "backend/sample_data/knowledge"
    langsmith_tracing: bool = False
    langsmith_project: str = "retriflow"
    llm_provider: str = "auto"
    chat_provider: str = "bailian"
    rewrite_provider: str = "ollama"
    route_provider: str = "ollama"
    memory_summary_provider: str = "ollama"
    intent_provider: str = "ollama"
    embedding_provider: str = "siliconflow"
    rerank_provider: str = "siliconflow"
    intent_confidence_threshold: float = 0.6
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_request_timeout_seconds: int = 30
    bailian_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    aihubmix_api_key: str = ""
    aihubmix_base_url: str = "https://aihubmix.com/v1"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embedding_model: str = "qwen3-embedding:8b"
    tika_enabled: bool = False
    tika_endpoint: str = "http://127.0.0.1:9998"
    tika_request_timeout_seconds: int = 60
    tika_ocr_enabled: bool = False
    tika_ocr_service_endpoint: str = "http://127.0.0.1:9889"
    tika_ocr_request_timeout_seconds: int = 30
    mcp_remote_enabled: bool = False
    mcp_remote_servers_json: str = "[]"
    mcp_remote_timeout_seconds: int = 15
    mcp_execution_mode: str = "sequential"
    mcp_max_tool_candidates: int = 3
    mcp_fail_fast: bool = False
    mcp_parallel_max_workers: int = 3
    route_use_llm: bool = False
    route_confidence_threshold: float = 0.45
    auth_enabled: bool = True
    auth_secret_key: str = "retriflow-dev-secret-key"
    auth_access_token_ttl_hours: int = 72
    memory_history_keep_turns: int = 8
    memory_summary_enabled: bool = True
    memory_summary_start_turns: int = 9
    memory_summary_max_chars: int = 240
    memory_short_ttl_days: int = 30
    memory_mid_enabled: bool = False
    memory_mid_max_items: int = 8
    memory_mid_ttl_days: int = 14
    memory_mid_prompt_max_items: int = 4
    memory_long_enabled: bool = False
    memory_long_max_items: int = 8
    memory_long_ttl_days: int = 180
    memory_long_prompt_max_items: int = 4
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


def _read_env_file() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@lru_cache
def get_settings() -> Settings:
    import os

    env_values = _read_env_file()

    def resolve(name: str, default: str) -> str:
        return os.getenv(name, env_values.get(name, default))

    def resolve_json_string(name: str, default: str) -> str:
        raw = resolve(name, default)
        try:
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            return default

    return Settings(
        database_backend=resolve("RETRIFLOW_DATABASE_BACKEND", "auto"),
        database_dsn=resolve("RETRIFLOW_DATABASE_DSN", ""),
        database_schema=resolve("RETRIFLOW_DATABASE_SCHEMA", "public"),
        db_path=resolve("RETRIFLOW_DB_PATH", "backend/data/retriflow.db"),
        seed_demo_content=resolve("RETRIFLOW_SEED_DEMO_CONTENT", "true").lower() == "true",
        allow_sqlite_fallback=resolve("RETRIFLOW_ALLOW_SQLITE_FALLBACK", "false").lower() == "true",
        workflow_adapter=resolve("RETRIFLOW_WORKFLOW_ADAPTER", "auto"),
        vector_store_type=resolve("RETRIFLOW_VECTOR_STORE_TYPE", "pg"),
        pgvector_dsn=resolve("RETRIFLOW_PGVECTOR_DSN", ""),
        pgvector_table=resolve("RETRIFLOW_PGVECTOR_TABLE", "retriflow_chunk_vectors"),
        default_chat_model=resolve("RETRIFLOW_DEFAULT_CHAT_MODEL", "qwen3-max"),
        deep_thinking_model=resolve("RETRIFLOW_DEEP_THINKING_MODEL", "qwen3-max"),
        default_embedding_model=resolve("RETRIFLOW_DEFAULT_EMBEDDING_MODEL", "qwen-emb-8b"),
        default_rerank_model=resolve("RETRIFLOW_DEFAULT_RERANK_MODEL", "Qwen/Qwen3-Reranker-8B"),
        retrieval_bm25_top_k=int(resolve("RETRIFLOW_RETRIEVAL_BM25_TOP_K", "80")),
        retrieval_vector_top_k=int(resolve("RETRIFLOW_RETRIEVAL_VECTOR_TOP_K", "80")),
        retrieval_rrf_top_k=int(resolve("RETRIFLOW_RETRIEVAL_RRF_TOP_K", "50")),
        retrieval_rerank_top_k=int(resolve("RETRIFLOW_RETRIEVAL_RERANK_TOP_K", "10")),
        retrieval_final_top_k=int(resolve("RETRIFLOW_RETRIEVAL_FINAL_TOP_K", "5")),
        default_route_model=resolve("RETRIFLOW_DEFAULT_ROUTE_MODEL", "qwen3-max"),
        sample_knowledge_dir=resolve("RETRIFLOW_SAMPLE_KNOWLEDGE_DIR", "backend/sample_data/knowledge"),
        langsmith_tracing=resolve("LANGSMITH_TRACING", "false").lower() == "true",
        langsmith_project=resolve("LANGSMITH_PROJECT", "retriflow"),
        llm_provider=resolve("RETRIFLOW_LLM_PROVIDER", "auto"),
        chat_provider=resolve("RETRIFLOW_CHAT_PROVIDER", "bailian"),
        rewrite_provider=resolve("RETRIFLOW_REWRITE_PROVIDER", "ollama"),
        route_provider=resolve("RETRIFLOW_ROUTE_PROVIDER", "ollama"),
        memory_summary_provider=resolve("RETRIFLOW_MEMORY_SUMMARY_PROVIDER", "ollama"),
        intent_provider=resolve("RETRIFLOW_INTENT_PROVIDER", "ollama"),
        embedding_provider=resolve("RETRIFLOW_EMBEDDING_PROVIDER", "siliconflow"),
        rerank_provider=resolve("RETRIFLOW_RERANK_PROVIDER", "siliconflow"),
        intent_confidence_threshold=float(resolve("RETRIFLOW_INTENT_CONFIDENCE_THRESHOLD", "0.6")),
        llm_api_key=resolve("RETRIFLOW_LLM_API_KEY", ""),
        llm_base_url=resolve("RETRIFLOW_LLM_BASE_URL", ""),
        llm_request_timeout_seconds=int(resolve("RETRIFLOW_LLM_REQUEST_TIMEOUT_SECONDS", "30")),
        bailian_api_key=resolve("BAILIAN_API_KEY", ""),
        dashscope_base_url=resolve("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        aihubmix_api_key=resolve("AIHUBMIX_API_KEY", ""),
        aihubmix_base_url=resolve("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
        siliconflow_api_key=resolve("SILICONFLOW_API_KEY", ""),
        siliconflow_base_url=resolve("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        deepseek_api_key=resolve("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=resolve("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        groq_api_key=resolve("GROQ_API_KEY", ""),
        groq_base_url=resolve("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        ollama_base_url=resolve("RETRIFLOW_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
        ollama_chat_model=resolve("RETRIFLOW_OLLAMA_CHAT_MODEL", "qwen3:8b"),
        ollama_embedding_model=resolve("RETRIFLOW_OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:8b"),
        tika_enabled=resolve("RETRIFLOW_TIKA_ENABLED", "false").lower() == "true",
        tika_endpoint=resolve("RETRIFLOW_TIKA_ENDPOINT", "http://127.0.0.1:9998"),
        tika_request_timeout_seconds=int(resolve("RETRIFLOW_TIKA_REQUEST_TIMEOUT_SECONDS", "60")),
        tika_ocr_enabled=resolve("RETRIFLOW_TIKA_OCR_ENABLED", "false").lower() == "true",
        tika_ocr_service_endpoint=resolve("RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT", "http://127.0.0.1:9889"),
        tika_ocr_request_timeout_seconds=int(resolve("RETRIFLOW_TIKA_OCR_REQUEST_TIMEOUT_SECONDS", "30")),
        mcp_remote_enabled=resolve("RETRIFLOW_MCP_REMOTE_ENABLED", "false").lower() == "true",
        mcp_remote_servers_json=resolve_json_string("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", "[]"),
        mcp_remote_timeout_seconds=int(resolve("RETRIFLOW_MCP_REMOTE_TIMEOUT_SECONDS", "15")),
        mcp_execution_mode=resolve("RETRIFLOW_MCP_EXECUTION_MODE", "sequential"),
        mcp_max_tool_candidates=int(resolve("RETRIFLOW_MCP_MAX_TOOL_CANDIDATES", "3")),
        mcp_fail_fast=resolve("RETRIFLOW_MCP_FAIL_FAST", "false").lower() == "true",
        mcp_parallel_max_workers=int(resolve("RETRIFLOW_MCP_PARALLEL_MAX_WORKERS", "3")),
        route_use_llm=resolve("RETRIFLOW_ROUTE_USE_LLM", "false").lower() == "true",
        route_confidence_threshold=float(resolve("RETRIFLOW_ROUTE_CONFIDENCE_THRESHOLD", "0.45")),
        auth_enabled=resolve("RETRIFLOW_AUTH_ENABLED", "true").lower() == "true",
        auth_secret_key=resolve("RETRIFLOW_AUTH_SECRET_KEY", "retriflow-dev-secret-key"),
        auth_access_token_ttl_hours=int(resolve("RETRIFLOW_AUTH_ACCESS_TOKEN_TTL_HOURS", "72")),
        memory_history_keep_turns=int(resolve("RETRIFLOW_MEMORY_HISTORY_KEEP_TURNS", "8")),
        memory_summary_enabled=resolve("RETRIFLOW_MEMORY_SUMMARY_ENABLED", "true").lower() == "true",
        memory_summary_start_turns=int(resolve("RETRIFLOW_MEMORY_SUMMARY_START_TURNS", "9")),
        memory_summary_max_chars=int(resolve("RETRIFLOW_MEMORY_SUMMARY_MAX_CHARS", "240")),
        memory_short_ttl_days=int(resolve("RETRIFLOW_MEMORY_SHORT_TTL_DAYS", "30")),
        memory_mid_enabled=resolve("RETRIFLOW_MEMORY_MID_ENABLED", "false").lower() == "true",
        memory_mid_max_items=int(resolve("RETRIFLOW_MEMORY_MID_MAX_ITEMS", "8")),
        memory_mid_ttl_days=int(resolve("RETRIFLOW_MEMORY_MID_TTL_DAYS", "14")),
        memory_mid_prompt_max_items=int(resolve("RETRIFLOW_MEMORY_MID_PROMPT_MAX_ITEMS", "4")),
        memory_long_enabled=resolve("RETRIFLOW_MEMORY_LONG_ENABLED", "false").lower() == "true",
        memory_long_max_items=int(resolve("RETRIFLOW_MEMORY_LONG_MAX_ITEMS", "8")),
        memory_long_ttl_days=int(resolve("RETRIFLOW_MEMORY_LONG_TTL_DAYS", "180")),
        memory_long_prompt_max_items=int(resolve("RETRIFLOW_MEMORY_LONG_PROMPT_MAX_ITEMS", "4")),
    )
