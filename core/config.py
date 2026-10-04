"""Environment-driven configuration for the self-healing engine."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Runtime settings loaded from environment variables."""

    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o")
    max_retries: int = Field(default=3, ge=1, le=5)
    instructor_max_retries: int = Field(default=2, ge=0, le=5)
    sandbox_timeout_seconds: int = Field(default=5, ge=1, le=60)
    sandbox_image: str = Field(default="self-healing-sandbox:latest")
    sandbox_mem_limit: str = Field(default="256m")
    sandbox_nano_cpus: int = Field(default=500_000_000)
    sandbox_pids_limit: int = Field(default=50)
    mock_llm: bool = Field(default=False)
    allow_local_sandbox: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=43127)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings parsed from the process environment."""
    api_key = os.getenv("OPENAI_API_KEY") or None
    mock_flag = os.getenv("MOCK_LLM", "").lower() in {"1", "true", "yes"}
    # Auto-enable mock LLM when no API key is present so the API remains demoable.
    mock_llm = mock_flag or not api_key

    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        instructor_max_retries=int(os.getenv("INSTRUCTOR_MAX_RETRIES", "2")),
        sandbox_timeout_seconds=int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "5")),
        sandbox_image=os.getenv("SANDBOX_IMAGE", "self-healing-sandbox:latest"),
        sandbox_mem_limit=os.getenv("SANDBOX_MEM_LIMIT", "256m"),
        sandbox_nano_cpus=int(os.getenv("SANDBOX_NANO_CPUS", "500000000")),
        sandbox_pids_limit=int(os.getenv("SANDBOX_PIDS_LIMIT", "50")),
        mock_llm=mock_llm,
        allow_local_sandbox=os.getenv("ALLOW_LOCAL_SANDBOX", "true").lower()
        in {"1", "true", "yes"},
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "43127")),
    )
