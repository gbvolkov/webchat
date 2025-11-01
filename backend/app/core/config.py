from functools import lru_cache
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-level configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHAT_", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    app_name: str = "GWP Chat Backend"
    api_prefix: str = "/api"
    llm_enabled: bool = True
    llm_api_base: str | None = None
    llm_api_scheme: str = "http"
    llm_api_host: str = "127.0.0.1"
    llm_api_port: int = 8080
    llm_api_path_prefix: str = "/v1"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_trace_enabled: bool = True
    search_enabled: bool = True
    embedding_model_name: str = "intfloat/multilingual-e5-large"
    embedding_batch_size: int = 8
    embedding_device: str | None = None
    chroma_persist_directory: str = "./.chroma"
    search_min_similarity: float = 0.3
    log_level: str = "WARNING"

    @property
    def llm_base_url(self) -> str:
        """Resolve the base URL for the OpenAI-compatible API."""
        if self.llm_api_base:
            return self.llm_api_base.rstrip("/")
        return f"{self.llm_api_scheme}://{self.llm_api_host}:{self.llm_api_port}".rstrip("/")

    @property
    def llm_path_prefix(self) -> str:
        """Return the normalized API path prefix for the OpenAI-compatible API."""
        prefix = (self.llm_api_path_prefix or "").strip()
        if not prefix:
            return ""
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        return prefix.rstrip("/")

    @property
    def llm_effective_base_url(self) -> str:
        """Return the base URL with the path prefix applied, preventing double prefixes."""
        base = self.llm_base_url.rstrip("/")
        prefix = self.llm_path_prefix
        if prefix and base.endswith(prefix):
            return base
        return f"{base}{prefix}" if prefix else base


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


class PaginationDefaults(BaseModel):
    """Common pagination defaults exposed via configuration."""

    limit: int = 20
    max_limit: int = 100


paging_defaults = PaginationDefaults()
