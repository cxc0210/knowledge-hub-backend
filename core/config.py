from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    mongodb_url: str
    mongodb_database: str
    elasticsearch_url: str
    elasticsearch_document_index: str = "kh_document_chunks_v1"
    elasticsearch_document_alias: str = "kh_document_chunks"
    embedding_base_url: str
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 16
    embedding_timeout_seconds: float = 120
    rag_keyword_top_k: int = 30
    rag_vector_top_k: int = 30
    rag_fusion_top_k: int = 20
    rag_rrf_k: int = 60
    rag_rerank_top_k: int = 8
    rag_context_max_chars: int = 12_000
    rag_rerank_content_max_chars: int = 1_200
    document_chunk_target_chars: int = 800
    document_chunk_max_chars: int = 1200
    document_chunk_min_chars: int = 200
    document_chunk_context_chars: int = 150
    document_index_worker_poll_seconds: float = 2
    document_index_recovery_interval_seconds: float = 60
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str | None = None
    llm_model: str = ""
    llm_temperature: float = 0
    llm_timeout_seconds: float = 120
    dashscope_api_key: SecretStr = SecretStr("")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    dashscope_asr_model: str = "qwen-audio-3.1-asr-flash"
    dashscope_asr_timeout_seconds: float = 120
    dashscope_asr_max_file_size_bytes: int = 20 * 1024 * 1024
    dashscope_tts_websocket_url: str = ""
    dashscope_tts_model: str = "qwen-audio-3.1-tts-flash"
    dashscope_tts_voice: str = "longanlingxin_v3.1"
    dashscope_tts_sample_rate: int = 24_000
    dashscope_tts_volume: int = 50
    dashscope_tts_rate: float = 1.0
    dashscope_tts_pitch: float = 1.0
    dashscope_tts_connect_timeout_seconds: float = 10
    ai_action_expire_minutes: int = 30
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from_email: str = "knowledge-hub@localhost"
    smtp_use_tls: bool = False
    smtp_start_tls: bool = False
    smtp_timeout_seconds: float = 30
    rustfs_endpoint: str
    rustfs_access_key: SecretStr
    rustfs_secret_key: SecretStr
    rustfs_bucket: str
    rustfs_presigned_url_expire_seconds: int = 900
    jwt_secret_key: SecretStr
    jwt_access_token_expire_minutes: int = 60
    auth_cookie_name: str = "kh_access_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cors_origins: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # pyright: ignore[reportCallIssue]
