from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model-agnostic provider switcher (local Ollama vs cloud live demo)
    llm_provider: Literal["ollama", "openai_compatible"] = "ollama"

    # Local Ollama defaults tuned for RTX 4060 8GB VRAM + 32GB DDR5 RAM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_embed_model: str = "qwen3-embedding:0.6b"
    ollama_num_ctx: int = 8192

    # OpenAI-compatible provider (Groq / OpenRouter / Gemini for hosted demo)
    openai_api_base: str = "https://api.groq.com/openai/v1"
    openai_api_key: str = ""
    openai_model: str = "llama-3.3-70b-versatile"

    # Paths (resolved relative to backend/ by default)
    data_dir: Path = Path("../data")
    config_dir: Path = Path("../config")
    duckdb_path: Path = Path("../data/market.duckdb")
    lancedb_path: Path = Path("../data/vectors.lancedb")
    market_cache_ttl_days: int = 7

    # API Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Phase 2: Arize Phoenix OpenTelemetry Observability
    enable_phoenix_tracing: bool = False
    phoenix_collector_endpoint: str = "http://localhost:6006/v1/traces"
    phoenix_ui_url: str = "http://localhost:6006"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def skills_taxonomy_path(self) -> Path:
        return self.config_dir / "skills_taxonomy.yaml"

    @property
    def ats_rules_path(self) -> Path:
        return self.config_dir / "ats_rules.yaml"

    @property
    def outputs_dir(self) -> Path:
        path = self.data_dir / "outputs"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
