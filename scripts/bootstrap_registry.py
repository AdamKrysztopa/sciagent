#!/usr/bin/env python3
"""Bootstrap the SciAgent user registry in GCP Secret Manager.

Usage:
    uv run python scripts/bootstrap_registry.py \\
        --project sciagent-496617 \\
        --slug admin \\
        --email admin@example.com \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from datetime import UTC, datetime

_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


def generate_key(slug: str) -> str:
    return f"agt_{slug}_{secrets.token_hex(16)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap SciAgent user registry")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--secret", default="agt-user-registry", help="Secret name")
    parser.add_argument("--slug", required=True, help="Admin slug, e.g. 'admin'")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument(
        "--budget", type=float, default=100.0, help="Admin LLM budget in USD (default: 100.0)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Add a new version even if one exists (old versions remain in Secret Manager)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be done without writing"
    )
    args = parser.parse_args()

    if not _SLUG_RE.match(args.slug):
        print(f"ERROR: --slug must match [a-z0-9_-]{{1,32}}, got: {args.slug!r}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        registry = {
            args.slug: {
                "key": "[dry-run-placeholder]",
                "email": args.email,
                "budget_usd": args.budget,
                "is_admin": True,
                "created_at": datetime.now(UTC).isoformat(),
            }
        }
        print("DRY RUN — would write:")
        print(json.dumps(registry, indent=2))
        print("\nGenerated key (NOT written): [dry-run-placeholder]")
        return

    key = generate_key(args.slug)
    registry = {
        args.slug: {
            "key": key,
            "email": args.email,
            "budget_usd": args.budget,
            "is_admin": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
    }
    payload = json.dumps(registry, indent=2).encode("utf-8")

    try:
        from google.cloud import secretmanager  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        print("ERROR: google-cloud-secret-manager not installed. Run: uv sync", file=sys.stderr)
        sys.exit(1)

    from google.api_core import exceptions as gcp_exceptions  # noqa: PLC0415

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{args.project}/secrets/{args.secret}"

    # Check for existing versions
    try:
        versions = list(client.list_secret_versions(request={"parent": parent}))  # type: ignore[misc]
        if versions and not args.force:
            print(
                f"ERROR: Secret {args.secret!r} already has {len(versions)} version(s).\n"
                "Use --force to add a new version (old versions remain in Secret Manager).",
                file=sys.stderr,
            )
            sys.exit(1)
    except gcp_exceptions.NotFound:
        # Secret does not exist yet — create it
        client.create_secret(  # type: ignore[misc]
            request={
                "parent": f"projects/{args.project}",
                "secret_id": args.secret,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"Created secret: {args.secret}")

    client.add_secret_version(request={"parent": parent, "payload": {"data": payload}})  # type: ignore[misc]

    print("\n" + "=" * 60)
    print(f"Registry bootstrapped: project={args.project} secret={args.secret}")
    print(f"Admin user: {args.slug} ({args.email})")
    print("\nAdmin API key (SAVE THIS — shown once):")
    print(f"  {key}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
