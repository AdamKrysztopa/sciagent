"""Runnable M1 example: foundation checks and startup readiness."""

from __future__ import annotations

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    resolve_xai_key,
)

from agt.config import Settings, configure_logging
from agt.guardrails import configure_guardrails
from agt.providers.router import build_provider
from agt.zotero.preflight import run_zotero_preflight


def main() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
    })
    configure_logging(settings.log_level)
    configure_guardrails(settings)

    try:
        provider = build_provider(settings)
        preflight = run_zotero_preflight(settings)
    except RuntimeError as exc:
        print("M1 Foundation Example")
        print(f"startup_error: {exc}")
        raise SystemExit(1) from exc

    print("M1 Foundation Example")
    print(f"provider: {settings.runtime.provider}")
    print(f"model: {settings.runtime.model_name}")
    print(f"provider_adapter: {provider.__class__.__name__}")
    print(f"zotero_preflight_ok: {preflight.ok}")
    print(f"zotero_preflight_message: {preflight.message}")


if __name__ == "__main__":
    main()
