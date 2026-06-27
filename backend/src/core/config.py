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
    default_embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    default_rerank_model: str = "qwen3-rerank"
    retrieval_bm25_top_k: int = 80
    retrieval_vector_top_k: int = 80
    retrieval_rrf_top_k: int = 50
    retrieval_rerank_top_k: int = 10
    retrieval_final_top_k: int = 5
    retrieval_cross_request_cache_enabled: bool = False
    retrieval_cross_request_cache_ttl_seconds: int = 60
    retrieval_cross_request_cache_max_entries: int = 256
    default_route_model: str = "qwen3-max"
    sample_knowledge_dir: str = "backend/sample_data/knowledge"
    storage_backend: str = "local"
    storage_local_dir: str = "backend/data/uploads"
    s3_endpoint: str = "http://127.0.0.1:9000"
    s3_access_key_id: str = "rustfsadmin"
    s3_secret_access_key: str = "rustfsadmin"
    s3_region: str = "us-east-1"
    langsmith_tracing: bool = False
    langsmith_project: str = "retriflow"
    llm_provider: str = "auto"
    chat_provider: str = "bailian"
    rewrite_provider: str = "bailian"
    route_provider: str = "bailian"
    memory_summary_provider: str = "bailian"
    intent_provider: str = "bailian"
    embedding_provider: str = "siliconflow"
    rerank_provider: str = "bailian"
    intent_confidence_threshold: float = 0.6
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_request_timeout_seconds: int = 30
    llm_stream_first_packet_timeout_seconds: float = 60.0
    model_health_failure_threshold: int = 3
    model_health_open_cooldown_seconds: int = 60
    model_health_probe_enabled: bool = False
    model_health_startup_probe_enabled: bool = False
    model_health_probe_interval_seconds: int = 300
    model_health_probe_capabilities: str = "chat,rewrite,route,intent,embedding,rerank"
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
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_chat_model: str = "unsloth/Qwen3.5-4B-GGUF"
    lmstudio_embedding_model: str = "Qwen/Qwen3-Embedding-8B-GGUF"
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
    chat_queue_enabled: bool = False
    chat_queue_backend: str = "memory"
    chat_queue_redis_url: str = "redis://127.0.0.1:6379/0"
    chat_queue_redis_key_prefix: str = "retriflow:chat"
    chat_queue_max_concurrent: int = 4
    chat_queue_max_wait_seconds: float = 30.0
    chat_queue_lease_seconds: int = 120
    chat_queue_poll_interval_ms: int = 100
    stream_task_cancel_redis_url: str = "redis://127.0.0.1:6379/0"
    stream_task_cancel_key_prefix: str = "retriflow:stream:cancel"
    stream_task_cancel_ttl_seconds: int = 1800
    distributed_lock_backend: str = "memory"
    distributed_lock_redis_url: str = "redis://127.0.0.1:6379/0"
    distributed_lock_key_prefix: str = "retriflow:lock"
    distributed_lock_ttl_seconds: int = 300
    route_use_llm: bool = False
    route_confidence_threshold: float = 0.45
    intent_tree_cache_enabled: bool = True
    intent_tree_cache_redis_url: str = "redis://127.0.0.1:6379/0"
    intent_tree_cache_key: str = "retriflow:intent:tree"
    intent_tree_cache_ttl_days: int = 7
    query_term_mapping_cache_enabled: bool = False
    query_term_mapping_cache_redis_url: str = "redis://127.0.0.1:6379/0"
    query_term_mapping_cache_key: str = "retriflow:query-term:mappings"
    query_term_mapping_cache_ttl_days: int = 7
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
        default_embedding_model=resolve("RETRIFLOW_DEFAULT_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B"),
        default_rerank_model=resolve("RETRIFLOW_DEFAULT_RERANK_MODEL", "qwen3-rerank"),
        retrieval_bm25_top_k=int(resolve("RETRIFLOW_RETRIEVAL_BM25_TOP_K", "80")),
        retrieval_vector_top_k=int(resolve("RETRIFLOW_RETRIEVAL_VECTOR_TOP_K", "80")),
        retrieval_rrf_top_k=int(resolve("RETRIFLOW_RETRIEVAL_RRF_TOP_K", "50")),
        retrieval_rerank_top_k=int(resolve("RETRIFLOW_RETRIEVAL_RERANK_TOP_K", "10")),
        retrieval_final_top_k=int(resolve("RETRIFLOW_RETRIEVAL_FINAL_TOP_K", "5")),
        retrieval_cross_request_cache_enabled=resolve("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_ENABLED", "false").lower() == "true",
        retrieval_cross_request_cache_ttl_seconds=int(resolve("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_TTL_SECONDS", "60")),
        retrieval_cross_request_cache_max_entries=int(resolve("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_MAX_ENTRIES", "256")),
        default_route_model=resolve("RETRIFLOW_DEFAULT_ROUTE_MODEL", "qwen3-max"),
        sample_knowledge_dir=resolve("RETRIFLOW_SAMPLE_KNOWLEDGE_DIR", "backend/sample_data/knowledge"),
        storage_backend=resolve("RETRIFLOW_STORAGE_BACKEND", "local"),
        storage_local_dir=resolve("RETRIFLOW_STORAGE_LOCAL_DIR", "backend/data/uploads"),
        s3_endpoint=resolve("RETRIFLOW_S3_ENDPOINT", "http://127.0.0.1:9000"),
        s3_access_key_id=resolve("RETRIFLOW_S3_ACCESS_KEY_ID", "rustfsadmin"),
        s3_secret_access_key=resolve("RETRIFLOW_S3_SECRET_ACCESS_KEY", "rustfsadmin"),
        s3_region=resolve("RETRIFLOW_S3_REGION", "us-east-1"),
        langsmith_tracing=resolve("LANGSMITH_TRACING", "false").lower() == "true",
        langsmith_project=resolve("LANGSMITH_PROJECT", "retriflow"),
        llm_provider=resolve("RETRIFLOW_LLM_PROVIDER", "auto"),
        chat_provider=resolve("RETRIFLOW_CHAT_PROVIDER", "bailian"),
        rewrite_provider=resolve("RETRIFLOW_REWRITE_PROVIDER", "bailian"),
        route_provider=resolve("RETRIFLOW_ROUTE_PROVIDER", "bailian"),
        memory_summary_provider=resolve("RETRIFLOW_MEMORY_SUMMARY_PROVIDER", "bailian"),
        intent_provider=resolve("RETRIFLOW_INTENT_PROVIDER", "bailian"),
        embedding_provider=resolve("RETRIFLOW_EMBEDDING_PROVIDER", "siliconflow"),
        rerank_provider=resolve("RETRIFLOW_RERANK_PROVIDER", "bailian"),
        intent_confidence_threshold=float(resolve("RETRIFLOW_INTENT_CONFIDENCE_THRESHOLD", "0.6")),
        llm_api_key=resolve("RETRIFLOW_LLM_API_KEY", ""),
        llm_base_url=resolve("RETRIFLOW_LLM_BASE_URL", ""),
        llm_request_timeout_seconds=int(resolve("RETRIFLOW_LLM_REQUEST_TIMEOUT_SECONDS", "30")),
        llm_stream_first_packet_timeout_seconds=float(
            resolve("RETRIFLOW_LLM_STREAM_FIRST_PACKET_TIMEOUT_SECONDS", "60")
        ),
        model_health_failure_threshold=int(resolve("RETRIFLOW_MODEL_HEALTH_FAILURE_THRESHOLD", "3")),
        model_health_open_cooldown_seconds=int(resolve("RETRIFLOW_MODEL_HEALTH_OPEN_COOLDOWN_SECONDS", "60")),
        model_health_probe_enabled=resolve("RETRIFLOW_MODEL_HEALTH_PROBE_ENABLED", "false").lower() == "true",
        model_health_startup_probe_enabled=resolve("RETRIFLOW_MODEL_HEALTH_STARTUP_PROBE_ENABLED", "false").lower()
        == "true",
        model_health_probe_interval_seconds=int(resolve("RETRIFLOW_MODEL_HEALTH_PROBE_INTERVAL_SECONDS", "300")),
        model_health_probe_capabilities=resolve(
            "RETRIFLOW_MODEL_HEALTH_PROBE_CAPABILITIES",
            "chat,rewrite,route,intent,embedding,rerank",
        ),
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
        lmstudio_base_url=resolve("RETRIFLOW_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        lmstudio_chat_model=resolve("RETRIFLOW_LMSTUDIO_CHAT_MODEL", "unsloth/Qwen3.5-4B-GGUF"),
        lmstudio_embedding_model=resolve("RETRIFLOW_LMSTUDIO_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B-GGUF"),
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
        chat_queue_enabled=resolve("RETRIFLOW_CHAT_QUEUE_ENABLED", "false").lower() == "true",
        chat_queue_backend=resolve("RETRIFLOW_CHAT_QUEUE_BACKEND", "memory"),
        chat_queue_redis_url=resolve("RETRIFLOW_CHAT_QUEUE_REDIS_URL", "redis://127.0.0.1:6379/0"),
        chat_queue_redis_key_prefix=resolve("RETRIFLOW_CHAT_QUEUE_REDIS_KEY_PREFIX", "retriflow:chat"),
        chat_queue_max_concurrent=int(resolve("RETRIFLOW_CHAT_QUEUE_MAX_CONCURRENT", "4")),
        chat_queue_max_wait_seconds=float(resolve("RETRIFLOW_CHAT_QUEUE_MAX_WAIT_SECONDS", "30")),
        chat_queue_lease_seconds=int(resolve("RETRIFLOW_CHAT_QUEUE_LEASE_SECONDS", "120")),
        chat_queue_poll_interval_ms=int(resolve("RETRIFLOW_CHAT_QUEUE_POLL_INTERVAL_MS", "100")),
        stream_task_cancel_redis_url=resolve("RETRIFLOW_STREAM_TASK_CANCEL_REDIS_URL", "redis://127.0.0.1:6379/0"),
        stream_task_cancel_key_prefix=resolve("RETRIFLOW_STREAM_TASK_CANCEL_KEY_PREFIX", "retriflow:stream:cancel"),
        stream_task_cancel_ttl_seconds=int(resolve("RETRIFLOW_STREAM_TASK_CANCEL_TTL_SECONDS", "1800")),
        distributed_lock_backend=resolve("RETRIFLOW_DISTRIBUTED_LOCK_BACKEND", "memory"),
        distributed_lock_redis_url=resolve("RETRIFLOW_DISTRIBUTED_LOCK_REDIS_URL", "redis://127.0.0.1:6379/0"),
        distributed_lock_key_prefix=resolve("RETRIFLOW_DISTRIBUTED_LOCK_KEY_PREFIX", "retriflow:lock"),
        distributed_lock_ttl_seconds=int(resolve("RETRIFLOW_DISTRIBUTED_LOCK_TTL_SECONDS", "300")),
        route_use_llm=resolve("RETRIFLOW_ROUTE_USE_LLM", "false").lower() == "true",
        route_confidence_threshold=float(resolve("RETRIFLOW_ROUTE_CONFIDENCE_THRESHOLD", "0.45")),
        intent_tree_cache_enabled=resolve("RETRIFLOW_INTENT_TREE_CACHE_ENABLED", "true").lower() == "true",
        intent_tree_cache_redis_url=resolve("RETRIFLOW_INTENT_TREE_CACHE_REDIS_URL", "redis://127.0.0.1:6379/0"),
        intent_tree_cache_key=resolve("RETRIFLOW_INTENT_TREE_CACHE_KEY", "retriflow:intent:tree"),
        intent_tree_cache_ttl_days=int(resolve("RETRIFLOW_INTENT_TREE_CACHE_TTL_DAYS", "7")),
        query_term_mapping_cache_enabled=resolve("RETRIFLOW_QUERY_TERM_MAPPING_CACHE_ENABLED", "false").lower() == "true",
        query_term_mapping_cache_redis_url=resolve("RETRIFLOW_QUERY_TERM_MAPPING_CACHE_REDIS_URL", "redis://127.0.0.1:6379/0"),
        query_term_mapping_cache_key=resolve("RETRIFLOW_QUERY_TERM_MAPPING_CACHE_KEY", "retriflow:query-term:mappings"),
        query_term_mapping_cache_ttl_days=int(resolve("RETRIFLOW_QUERY_TERM_MAPPING_CACHE_TTL_DAYS", "7")),
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
