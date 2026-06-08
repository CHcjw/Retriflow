from functools import lru_cache
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
    workflow_adapter: str = "auto"
    vector_store_type: str = "pg"
    pgvector_dsn: str = ""
    pgvector_table: str = "retriflow_chunk_vectors"
    default_chat_model: str = "qwen3-max"
    deep_thinking_model: str = "qwen3-max"
    default_embedding_model: str = "qwen-emb-8b"
    default_rerank_model: str = "qwen3-rerank"
    default_route_model: str = "qwen3-max"
    sample_knowledge_dir: str = "backend/sample_data/knowledge"
    langsmith_tracing: bool = False
    langsmith_project: str = "retriflow"
    llm_provider: str = "auto"
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
    tika_enabled: bool = False
    tika_endpoint: str = "http://127.0.0.1:9998"
    tika_request_timeout_seconds: int = 60
    tika_ocr_enabled: bool = False
    tika_ocr_service_endpoint: str = "http://127.0.0.1:9889"
    tika_ocr_request_timeout_seconds: int = 30
    route_use_llm: bool = False
    route_confidence_threshold: float = 0.45
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

    return Settings(
        database_backend=resolve("RETRIFLOW_DATABASE_BACKEND", "auto"),
        database_dsn=resolve("RETRIFLOW_DATABASE_DSN", ""),
        database_schema=resolve("RETRIFLOW_DATABASE_SCHEMA", "public"),
        db_path=resolve("RETRIFLOW_DB_PATH", "backend/data/retriflow.db"),
        workflow_adapter=resolve("RETRIFLOW_WORKFLOW_ADAPTER", "auto"),
        vector_store_type=resolve("RETRIFLOW_VECTOR_STORE_TYPE", "pg"),
        pgvector_dsn=resolve("RETRIFLOW_PGVECTOR_DSN", ""),
        pgvector_table=resolve("RETRIFLOW_PGVECTOR_TABLE", "retriflow_chunk_vectors"),
        default_chat_model=resolve("RETRIFLOW_DEFAULT_CHAT_MODEL", "qwen3-max"),
        deep_thinking_model=resolve("RETRIFLOW_DEEP_THINKING_MODEL", "qwen3-max"),
        default_embedding_model=resolve("RETRIFLOW_DEFAULT_EMBEDDING_MODEL", "qwen-emb-8b"),
        default_rerank_model=resolve("RETRIFLOW_DEFAULT_RERANK_MODEL", "qwen3-rerank"),
        default_route_model=resolve("RETRIFLOW_DEFAULT_ROUTE_MODEL", "qwen3-max"),
        sample_knowledge_dir=resolve("RETRIFLOW_SAMPLE_KNOWLEDGE_DIR", "backend/sample_data/knowledge"),
        langsmith_tracing=resolve("LANGSMITH_TRACING", "false").lower() == "true",
        langsmith_project=resolve("LANGSMITH_PROJECT", "retriflow"),
        llm_provider=resolve("RETRIFLOW_LLM_PROVIDER", "auto"),
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
        tika_enabled=resolve("RETRIFLOW_TIKA_ENABLED", "false").lower() == "true",
        tika_endpoint=resolve("RETRIFLOW_TIKA_ENDPOINT", "http://127.0.0.1:9998"),
        tika_request_timeout_seconds=int(resolve("RETRIFLOW_TIKA_REQUEST_TIMEOUT_SECONDS", "60")),
        tika_ocr_enabled=resolve("RETRIFLOW_TIKA_OCR_ENABLED", "false").lower() == "true",
        tika_ocr_service_endpoint=resolve("RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT", "http://127.0.0.1:9889"),
        tika_ocr_request_timeout_seconds=int(resolve("RETRIFLOW_TIKA_OCR_REQUEST_TIMEOUT_SECONDS", "30")),
        route_use_llm=resolve("RETRIFLOW_ROUTE_USE_LLM", "false").lower() == "true",
        route_confidence_threshold=float(resolve("RETRIFLOW_ROUTE_CONFIDENCE_THRESHOLD", "0.45")),
    )
