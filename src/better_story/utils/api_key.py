from __future__ import annotations

import getpass
import os


def resolve_api_key(
    provider: str,
    *,
    cli_api_key: str | None = None,
    prompt_api_key: bool = False,
) -> str | None:
    if provider == "mock":
        return None
    if cli_api_key:
        return cli_api_key
    env_name = f"{provider.upper()}_API_KEY"
    if os.getenv(env_name):
        return os.getenv(env_name)
    if provider in {"openai", "openai_compatible"} and os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")
    if prompt_api_key:
        return getpass.getpass(f"Enter {provider} API key: ").strip()
    return None
