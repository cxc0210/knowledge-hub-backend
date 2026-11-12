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
