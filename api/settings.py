"""Settings for the API, read from environment variables (and .env).

The same code runs on your laptop and on a server; only these values change.
On your laptop they come from .env; on a host (Render, Railway, Fly...) you
set them in its dashboard. Each field below maps to an UPPER_CASE variable:
`cors_origins` is read from CORS_ORIGINS.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Websites allowed to call this API from a browser (see CORS in main.py).
    # The defaults are where the React dev server (Vite) runs. In .env, write a
    # JSON list:  CORS_ORIGINS=["http://localhost:5173","https://my-app.vercel.app"]
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Needed only by POST /ask.
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Read the settings once, then reuse the same object."""
    return Settings()
