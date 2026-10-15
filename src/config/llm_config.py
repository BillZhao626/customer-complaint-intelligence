from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str | None
    base_url: str | None
    model_name: str
    enable_api: bool
    temperature: float
    max_tokens: int

    @property
    def is_configured(self) -> bool:
        return self.enable_api and bool(self.api_key)

    @property
    def api_enabled(self) -> bool:
        return self.enable_api

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def validation_errors(self) -> list[str]:
        errors = []
        if self.enable_api and not self.api_key:
            errors.append("LLM_ENABLE_API=true requires LLM_API_KEY.")
        if self.enable_api and self.provider != "deepseek":
            errors.append(f"Unsupported LLM_PROVIDER: {self.provider}.")
        return errors

    def safe_summary(self) -> dict[str, object]:
        return {
            "enabled": self.enable_api,
            "provider": self.provider,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "api_key_configured": bool(self.api_key),
        }


def _load_dotenv_if_present() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_llm_config() -> LLMConfig:
    """Read optional LLM settings without requiring them for offline use."""

    _load_dotenv_if_present()
    enable_api = os.getenv("LLM_ENABLE_API", "false").strip().lower() in {"1", "true", "yes"}
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1200"))
    return LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "deepseek").strip().lower(),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        model_name=os.getenv("LLM_MODEL_NAME", "deepseek-v4-flash"),
        enable_api=enable_api,
        temperature=temperature,
        max_tokens=max_tokens,
    )
