# Email Welcome & Invite System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a formatted HTML welcome email containing the user's API key when an admin creates a new user, and allow re-sending that email from the Users table.

**Architecture:** Add an `html` parameter to the existing `send_email()` function, introduce a new `email_templates.py` module with the welcome email template, wire the template call into `create_key` (fire-and-forget, never blocks the 201 response), and add a `POST /admin/keys/{slug}/email` resend endpoint. Two small frontend changes: a confirmation line on the CreateUser success screen and a "Resend invite" button per row in the Users table.

**Tech Stack:** Python 3.14 · FastAPI · httpx · Resend HTTP API · React 18 · TypeScript · TanStack Query · Tailwind CSS

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/agt/email.py` | Modify | Add optional `html` parameter to `send_email()` |
| `src/agt/email_templates.py` | **Create** | `welcome_email()` → `(subject, text, html)` |
| `src/agt/config.py` | Modify | Add `service_url` and `email_support` fields |
| `src/agt/api/admin.py` | Modify | Import + call `send_email` in `create_key`; add resend endpoint |
| `tests/test_email.py` | **Create** | Tests for `send_email` html payload inclusion |
| `tests/test_email_templates.py` | **Create** | Tests for `welcome_email` output correctness |
| `tests/test_admin_endpoints.py` | Modify | Update `_FakeSettings`; add email-on-create and resend tests |
| `admin-panel/src/api.ts` | Modify | Add `resendInvite` method |
| `admin-panel/src/pages/CreateUser.tsx` | Modify | Show "email sent" confirmation in success state |
| `admin-panel/src/pages/Users.tsx` | Modify | Add "Resend invite" button per row |
| `NOTES.local.md` | Modify | Add Resend homework checklist + email env vars |

---

## Task 1: Add `html` parameter to `send_email()`

**Files:**
- Modify: `src/agt/email.py`
- Create: `tests/test_email.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_email.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_send_email_includes_html_when_provided() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = None

        from agt.email import send_email  # noqa: PLC0415

        await send_email(
            api_key="re_test",
            from_address="from@example.com",
            to=["to@example.com"],
            subject="Hello",
            text="Plain text",
            html="<p>HTML text</p>",
        )

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["html"] == "<p>HTML text</p>"


@pytest.mark.anyio
async def test_send_email_omits_html_when_not_provided() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = None

        from agt.email import send_email  # noqa: PLC0415

        await send_email(
            api_key="re_test",
            from_address="from@example.com",
            to=["to@example.com"],
            subject="Hello",
            text="Plain text",
        )

    payload = mock_client.post.call_args.kwargs["json"]
    assert "html" not in payload


@pytest.mark.anyio
async def test_send_email_noop_when_no_api_key() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        from agt.email import send_email  # noqa: PLC0415

        await send_email(
            api_key="",
            from_address="from@example.com",
            to=["to@example.com"],
            subject="Hello",
            text="Plain text",
        )

    mock_cls.assert_not_called()
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_email.py -v
```

Expected: `FAILED test_send_email_includes_html_when_provided` — `send_email()` doesn't accept `html` yet.

- [ ] **Step 3: Implement — update `src/agt/email.py`**

Replace the entire file:

```python
"""Transactional email sender (Resend / SendGrid compatible)."""

from __future__ import annotations

import structlog

_log = structlog.get_logger()


async def send_email(
    *,
    api_key: str,
    from_address: str,
    to: list[str],
    subject: str,
    text: str,
    html: str | None = None,
) -> None:
    """Send a plain-text (or HTML) email via Resend (POST /emails).

    Falls back to a log-only no-op when api_key is empty, so dev/test
    environments never make real network calls.
    """
    if not api_key:
        _log.info("email_send_skipped_no_key", to=to, subject=subject)
        return

    import httpx  # noqa: PLC0415

    payload: dict[str, object] = {
        "from": from_address,
        "to": to,
        "subject": subject,
        "text": text,
    }
    if html is not None:
        payload["html"] = html

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        _log.info("email_sent", to=to, subject=subject, status=response.status_code)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
uv run pytest tests/test_email.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/agt/email.py tests/test_email.py
uv run ruff format --check src/agt/email.py tests/test_email.py
uv run pyright src/agt/email.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/agt/email.py tests/test_email.py
git commit -m "feat: add html parameter to send_email()"
```

---

## Task 2: Create `email_templates.py` with `welcome_email()`

**Files:**
- Create: `src/agt/email_templates.py`
- Create: `tests/test_email_templates.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_email_templates.py`:

```python
from __future__ import annotations

from agt.email_templates import welcome_email


def test_welcome_email_subject_contains_welcome() -> None:
    subject, _, _ = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "welcome" in subject.lower() or "Welcome" in subject


def test_welcome_email_key_appears_in_text_and_html() -> None:
    _, text, html = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "agt_alice_abc123def456" in text
    assert "agt_alice_abc123def456" in html


def test_welcome_email_slug_appears_in_text_and_html() -> None:
    _, text, html = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "alice" in text
    assert "alice" in html


def test_welcome_email_service_url_in_text() -> None:
    _, text, html = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "https://sciagent.example.com" in text
    assert "https://sciagent.example.com" in html


def test_welcome_email_support_email_in_text() -> None:
    _, text, _ = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "support@example.com" in text


def test_welcome_email_html_is_complete_document() -> None:
    _, _, html = welcome_email(
        slug="alice",
        key="agt_alice_abc123def456",
        service_url="https://sciagent.example.com",
        support_email="support@example.com",
    )
    assert "<html" in html
    assert "</html>" in html
    assert "<body" in html


def test_welcome_email_returns_nonempty_strings() -> None:
    subject, text, html = welcome_email(
        slug="bob",
        key="agt_bob_xyz",
        service_url="https://example.com",
        support_email="s@example.com",
    )
    assert subject.strip()
    assert text.strip()
    assert html.strip()
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_email_templates.py -v
```

Expected: `ModuleNotFoundError: No module named 'agt.email_templates'`

- [ ] **Step 3: Implement — create `src/agt/email_templates.py`**

```python
"""Email templates for transactional emails."""

from __future__ import annotations

_WELCOME_SUBJECT = "Welcome to SciAgent — your API key is ready"

_WELCOME_TEXT = """\
Hi {slug},

Welcome to SciAgent! Your API key is ready:

  {key}

Keep this key safe — treat it like a password.

Getting started (3 steps):
  1. Install the SciAgent Zotero add-on
  2. Open Zotero and find the SciAgent sidebar
  3. Paste your API key and start searching

Service URL: {service_url}

A full user manual is coming soon.

Questions or issues? Contact us at {support_email} — we reply within one business day.

— The SciAgent team
"""

_WELCOME_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      margin: 0; padding: 0; background: #f4f4f5; color: #18181b;
    }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #fff;
                border-radius: 8px; overflow: hidden;
                box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .header {{ background: #1e3a5f; color: #fff; padding: 28px 32px; }}
    .header h1 {{ margin: 0 0 4px; font-size: 22px; letter-spacing: -0.3px; }}
    .header p {{ margin: 0; color: #93c5fd; font-size: 13px; }}
    .body {{ padding: 32px; }}
    .body p {{ line-height: 1.6; margin: 0 0 16px; }}
    .key-box {{
      background: #f4f4f5; border: 1px solid #d4d4d8; border-radius: 6px;
      padding: 16px; margin: 20px 0;
    }}
    .key-box code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 14px; word-break: break-all; color: #18181b;
    }}
    .key-hint {{ font-size: 12px; color: #71717a; margin-top: 8px; }}
    .steps {{ padding-left: 20px; margin: 0 0 20px; }}
    .steps li {{ padding: 6px 0; line-height: 1.5; }}
    .cta {{ text-align: center; margin: 28px 0; }}
    .cta a {{
      display: inline-block; background: #2563eb; color: #fff;
      padding: 12px 28px; border-radius: 6px; text-decoration: none;
      font-weight: 600; font-size: 14px;
    }}
    .manual-note {{
      background: #eff6ff; border-left: 3px solid #93c5fd;
      padding: 12px 16px; border-radius: 0 4px 4px 0;
      font-size: 13px; color: #1e40af; margin: 20px 0;
    }}
    .footer {{
      border-top: 1px solid #e4e4e7; padding: 20px 32px;
      font-size: 12px; color: #71717a; text-align: center;
    }}
    .footer a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>SciAgent</h1>
      <p>Federated academic paper search</p>
    </div>
    <div class="body">
      <p>Hi <strong>{slug}</strong>,</p>
      <p>Your SciAgent account is ready. Here is your API key:</p>
      <div class="key-box">
        <code>{key}</code>
        <p class="key-hint">Keep this key safe — treat it like a password.</p>
      </div>
      <p><strong>Getting started in 3 steps:</strong></p>
      <ol class="steps">
        <li>Install the SciAgent Zotero add-on</li>
        <li>Open Zotero and find the <em>SciAgent</em> sidebar</li>
        <li>Paste your API key and start searching</li>
      </ol>
      <div class="cta">
        <a href="{service_url}">Open SciAgent</a>
      </div>
      <div class="manual-note">
        A full user manual is coming soon — we will send it to this address when it is ready.
      </div>
    </div>
    <div class="footer">
      <p>
        Questions? Reply to this email or contact
        <a href="mailto:{support_email}">{support_email}</a>
      </p>
      <p>SciAgent &mdash; federated academic search</p>
    </div>
  </div>
</body>
</html>
"""


def welcome_email(
    *,
    slug: str,
    key: str,
    service_url: str,
    support_email: str,
) -> tuple[str, str, str]:
    """Return (subject, plain_text, html) for a new-user welcome email."""
    text = _WELCOME_TEXT.format(
        slug=slug,
        key=key,
        service_url=service_url,
        support_email=support_email,
    )
    html = _WELCOME_HTML.format(
        slug=slug,
        key=key,
        service_url=service_url,
        support_email=support_email,
    )
    return _WELCOME_SUBJECT, text, html
```

- [ ] **Step 4: Run tests — all should pass**

```bash
uv run pytest tests/test_email_templates.py -v
```

Expected: 7 PASSED.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/agt/email_templates.py tests/test_email_templates.py
uv run ruff format --check src/agt/email_templates.py tests/test_email_templates.py
uv run pyright src/agt/email_templates.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/agt/email_templates.py tests/test_email_templates.py
git commit -m "feat: add welcome email template"
```

---

## Task 3: Add `service_url` and `email_support` to `Settings`

**Files:**
- Modify: `src/agt/config.py` (after line 116, after the `email_from` field)
- Modify: `tests/test_admin_endpoints.py` (`_FakeSettings` dataclass)

- [ ] **Step 1: Add fields to `src/agt/config.py`**

Find the `email_from` field (lines 113–117). Insert after it:

```python
    service_url: str = Field(
        default="https://sciagent-ewpafdgfya-ew.a.run.app",
        validation_alias=AliasChoices("AGT_SERVICE_URL", "SERVICE_URL"),
        description="Public service URL included in welcome emails.",
    )
    email_support: str = Field(
        default="krysztopa@gmail.com",
        validation_alias=AliasChoices("AGT_EMAIL_SUPPORT", "EMAIL_SUPPORT"),
        description="Support reply-to address shown in welcome emails.",
    )
```

- [ ] **Step 2: Update `_FakeSettings` in `tests/test_admin_endpoints.py`**

Find the `_FakeSettings` dataclass (around line 15) and add the two new fields:

```python
@dataclass(slots=True)
class _FakeSettings:
    email_api_key: object = None
    email_from: str = "noreply@test.example"
    service_url: str = "https://sciagent.example.com"
    email_support: str = "support@example.com"
```

- [ ] **Step 3: Verify pyright and existing tests still pass**

```bash
uv run pyright src/agt/config.py
uv run pytest tests/test_config.py tests/test_admin_endpoints.py -v
```

Expected: all PASSED, no pyright errors.

- [ ] **Step 4: Commit**

```bash
git add src/agt/config.py tests/test_admin_endpoints.py
git commit -m "feat: add service_url and email_support config fields"
```

---

## Task 4: Wire welcome email into `create_key`; add resend endpoint

**Files:**
- Modify: `src/agt/api/admin.py`
- Modify: `tests/test_admin_endpoints.py`

- [ ] **Step 1: Write failing tests — add to `tests/test_admin_endpoints.py`**

Add these two test classes at the end of the file:

```python
from unittest.mock import AsyncMock, patch


class TestCreateKeyEmail:
    def test_welcome_email_sent_on_create(self) -> None:
        app, _ = _make_app()
        with patch("agt.api.admin.send_email", new_callable=AsyncMock) as mock_send:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/keys",
                    json={"slug": "alice", "email": "alice@example.com"},
                    headers={"X-AGT-API-Key": _ADMIN_KEY},
                )
        assert resp.status_code == HTTP_CREATED
        mock_send.assert_awaited_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["to"] == ["alice@example.com"]
        assert "alice" in kwargs["text"]
        assert kwargs["html"] is not None

    def test_create_succeeds_even_if_email_fails(self) -> None:
        app, registry = _make_app()
        with patch(
            "agt.api.admin.send_email",
            new_callable=AsyncMock,
            side_effect=Exception("SMTP down"),
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/keys",
                    json={"slug": "carol", "email": "carol@example.com"},
                    headers={"X-AGT-API-Key": _ADMIN_KEY},
                )
        assert resp.status_code == HTTP_CREATED
        assert "carol" in registry.get_all()


class TestResendInvite:
    def test_resend_sends_email_to_user(self) -> None:
        app, _ = _make_app()
        with patch("agt.api.admin.send_email", new_callable=AsyncMock) as mock_send:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/keys/bob/email",
                    headers={"X-AGT-API-Key": _ADMIN_KEY},
                )
        assert resp.status_code == HTTP_OK
        mock_send.assert_awaited_once()
        assert mock_send.call_args.kwargs["to"] == ["bob@example.com"]

    def test_resend_404_for_unknown_slug(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/admin/keys/nobody/email",
                headers={"X-AGT-API-Key": _ADMIN_KEY},
            )
        assert resp.status_code == HTTP_NOT_FOUND

    def test_resend_returns_status_sent(self) -> None:
        app, _ = _make_app()
        with patch("agt.api.admin.send_email", new_callable=AsyncMock):
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/keys/bob/email",
                    headers={"X-AGT-API-Key": _ADMIN_KEY},
                )
        assert resp.json()["status"] == "sent"
```

- [ ] **Step 2: Run to confirm new tests fail**

```bash
uv run pytest tests/test_admin_endpoints.py::TestCreateKeyEmail tests/test_admin_endpoints.py::TestResendInvite -v
```

Expected: FAILED — `send_email` not imported, resend endpoint doesn't exist.

- [ ] **Step 3: Update `src/agt/api/admin.py`**

Add two imports after the existing `from agt.secrets import ...` line:

```python
from agt.email import send_email
from agt.email_templates import welcome_email as _make_welcome_email
```

Replace the `create_key` endpoint body (lines 80–99) with:

```python
    @router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
    async def create_key(body: CreateKeyRequest) -> CreateKeyResponse:  # pyright: ignore[reportUnusedFunction]
        registry = get_registry()
        users = registry.get_all()
        if body.slug in users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {body.slug!r} already exists",
            )
        budget = body.budget_usd if body.budget_usd is not None else default_budget
        key = generate_key(body.slug)
        entry = UserEntry(
            key=key,
            email=body.email,
            budget_usd=budget,
            is_admin=False,
            created_at=datetime.now(UTC).isoformat(),
        )
        users[body.slug] = entry
        registry.update(users)
        email_key = settings.email_api_key.get_secret_value() if settings.email_api_key else ""
        subject, text, html = _make_welcome_email(
            slug=body.slug,
            key=key,
            service_url=settings.service_url,
            support_email=settings.email_support,
        )
        try:
            await send_email(
                api_key=email_key,
                from_address=settings.email_from,
                to=[body.email],
                subject=subject,
                text=text,
                html=html,
            )
        except Exception:
            _log.warning("welcome_email_failed", slug=body.slug)
        return CreateKeyResponse(slug=body.slug, key=key, email=body.email, budget_usd=budget)
```

Add `import structlog` and `_log = structlog.get_logger()` near the top of the file (after the existing imports), and add the resend endpoint inside `create_admin_router` before `return router`:

```python
    @router.post("/keys/{slug}/email")
    async def resend_invite(slug: str) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        registry = get_registry()
        users = registry.get_all()
        if slug not in users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {slug!r} not found",
            )
        entry = users[slug]
        email_key = settings.email_api_key.get_secret_value() if settings.email_api_key else ""
        subject, text, html = _make_welcome_email(
            slug=slug,
            key=entry.key,
            service_url=settings.service_url,
            support_email=settings.email_support,
        )
        try:
            await send_email(
                api_key=email_key,
                from_address=settings.email_from,
                to=[entry.email],
                subject=subject,
                text=text,
                html=html,
            )
        except Exception:
            _log.warning("resend_invite_email_failed", slug=slug)
        return {"status": "sent", "slug": slug}
```

- [ ] **Step 4: Run all admin tests**

```bash
uv run pytest tests/test_admin_endpoints.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Quality gate**

```bash
uv run ruff check src/agt/api/admin.py
uv run ruff format --check src/agt/api/admin.py
uv run pyright src/agt/api/admin.py
```

Expected: no errors.

- [ ] **Step 6: Full Python test suite**

```bash
uv run pytest -q --vcr-record=none
```

Expected: all PASSED (no regressions).

- [ ] **Step 7: Commit**

```bash
git add src/agt/api/admin.py tests/test_admin_endpoints.py
git commit -m "feat: send welcome email on user create; add resend invite endpoint"
```

---

## Task 5: Frontend — add `resendInvite` to `api.ts`

**Files:**
- Modify: `admin-panel/src/api.ts`

- [ ] **Step 1: Add `resendInvite` to the `api` object**

Open `admin-panel/src/api.ts`. At the end of the `api` object (before the closing `};`), add:

```ts
  resendInvite: (apiKey: string, slug: string) =>
    apiFetch<{ status: string }>(`/admin/keys/${slug}/email`, apiKey, {
      method: "POST",
    }),
```

- [ ] **Step 2: Typecheck**

```bash
cd admin-panel && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add admin-panel/src/api.ts
git commit -m "feat: add resendInvite API method"
```

---

## Task 6: Frontend — show email confirmation in `CreateUser.tsx`

**Files:**
- Modify: `admin-panel/src/pages/CreateUser.tsx`

- [ ] **Step 1: Add `createdEmail` state and update success state**

Add a `createdEmail` state alongside `createdKey`:

```tsx
  const [createdEmail, setCreatedEmail] = useState<string | null>(null);
```

In `handleSubmit`, after `setCreatedKey(resp.key)` add:

```tsx
      setCreatedEmail(resp.email);
```

Replace the `createdKey !== null` success block with:

```tsx
  if (createdKey !== null) {
    return (
      <div className="bg-white p-6 rounded shadow max-w-md">
        <h2 className="text-xl font-bold mb-4 text-green-700">User Created</h2>
        <p className="mb-2">
          API key for <strong>{slug}</strong>:
        </p>
        <code className="block bg-gray-100 p-3 rounded break-all mb-4">
          {createdKey}
        </code>
        <p className="text-sm text-gray-500 mb-4">
          Copy this key now — it cannot be shown again.
        </p>
        <p className="text-sm text-green-600 mb-4">
          Welcome email sent to <strong>{createdEmail}</strong> with the key and getting-started
          instructions.
        </p>
        <button
          onClick={onCreated}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Done
        </button>
      </div>
    );
  }
```

- [ ] **Step 2: Build and typecheck**

```bash
cd admin-panel && npm run build && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add admin-panel/src/pages/CreateUser.tsx
git commit -m "feat: show email confirmation after user creation"
```

---

## Task 7: Frontend — "Resend invite" button in `Users.tsx`

**Files:**
- Modify: `admin-panel/src/pages/Users.tsx`

- [ ] **Step 1: Add `resendInvite` mutation and per-row state**

Add the mutation after the existing `revoke` mutation:

```tsx
  const [resentSlug, setResentSlug] = useState<string | null>(null);

  const resend = useMutation({
    mutationFn: (slug: string) => api.resendInvite(apiKey, slug),
    onSuccess: (_data, slug) => {
      setResentSlug(slug);
      setTimeout(() => setResentSlug(null), 2000);
    },
  });
```

- [ ] **Step 2: Add `useState` import**

`useState` must be imported. Update the import line at the top:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
```

- [ ] **Step 3: Add "Resend invite" button in each row**

In the `<td className="p-3">` that currently contains only the Revoke button, add the Resend button alongside it:

```tsx
                <td className="p-3 flex gap-2 items-center">
                  <button
                    onClick={() => resend.mutate(u.slug)}
                    className="text-blue-600 hover:underline text-sm"
                    disabled={resend.isPending}
                  >
                    {resentSlug === u.slug ? "Sent!" : "Resend invite"}
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Revoke ${u.slug}?`)) revoke.mutate(u.slug);
                    }}
                    className="text-red-600 hover:underline text-sm"
                    disabled={revoke.isPending}
                  >
                    Revoke
                  </button>
                </td>
```

- [ ] **Step 4: Build, lint, and typecheck**

```bash
cd admin-panel && npm run lint && npm run build && npm run typecheck
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add admin-panel/src/pages/Users.tsx
git commit -m "feat: add Resend invite button to Users table"
```

---

## Task 8: Update `NOTES.local.md` with homework and email env vars

**Files:**
- Modify: `NOTES.local.md` (not tracked in git — just update the file)

- [ ] **Step 1: Add "Email Setup Homework" section**

Insert after the `## Deploy` section:

```markdown
## Email Setup — Homework (do before deploying email feature)

### Step 1 — Sign up for Resend

1. Go to <https://resend.com> and create a free account
2. In the dashboard, go to **API Keys** → **Create API key**
   - Name: `sciagent-production`
   - Permission: Sending access
3. Copy the key (`re_...`) — it is shown only once

### Step 2 — Verify mechai.pl domain

1. In Resend dashboard, go to **Domains** → **Add Domain**
2. Enter `mechai.pl`
3. Resend shows 3 DNS TXT records — copy them
4. Go to **Google Workspace Admin** → Domains → mechai.pl → DNS records
5. Add each TXT record exactly as shown
6. Back in Resend, click **Verify** — wait ~5 min; status should turn green

### Step 3 — Store the key in GCP Secret Manager

```bash
PROJECT=sciagent-496617
SA=sciagent-backend@sciagent-496617.iam.gserviceaccount.com

# Create secret
gcloud secrets create agt-email-api-key \
  --replication-policy=automatic \
  --project=$PROJECT

# Set value (replace re_YOUR_KEY)
echo -n "re_YOUR_KEY" | gcloud secrets versions add agt-email-api-key \
  --data-file=- --project=$PROJECT

# Grant SA access
gcloud secrets add-iam-policy-binding agt-email-api-key \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT
```

### Step 4 — Wire env vars into Cloud Run

```bash
gcloud run services update sciagent \
  --update-env-vars="AGT_EMAIL_API_KEY=re_YOUR_KEY,AGT_EMAIL_FROM=sciagent@mechai.pl" \
  --region=europe-west1 \
  --project=sciagent-496617
```

### Step 5 — Verify with a test user creation

Log into the admin panel and create a test user with your own email.
Check your inbox for the welcome email within ~30 seconds.

- [ ] **Step 2: Update the "Environment variables set on the revision" table**

Add the two new variables to the env var block:

```text
AGT_GCP_PROJECT=sciagent-496617
AGT_GCP_SECRET_NAME=agt-user-registry
AGT_SECRET_CACHE_TTL_SECONDS=60
AGT_EMAIL_API_KEY=re_...          ← set after Resend signup
AGT_EMAIL_FROM=sciagent@mechai.pl ← set after domain verification
```

---

## Task 9: Final quality gates and deploy

- [ ] **Step 1: Full Python quality gate**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

Expected: all pass, zero pyright errors.

- [ ] **Step 2: Full frontend quality gate**

```bash
cd admin-panel && npm ci && npm run lint && npm run build && npm run typecheck && npm run test
```

Expected: all pass.

- [ ] **Step 3: Docs lint**

```bash
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md"
```

Expected: no errors.

- [ ] **Step 4: Deploy**

```bash
./scripts/deploy.sh
```

Expected: Cloud Build completes, new revision deployed.

- [ ] **Step 5: Smoke test**

Complete the Resend homework in NOTES.local.md (Tasks 1–4 of the homework checklist) first, then create a test user from the admin panel and confirm the welcome email arrives.

---

## Self-Review Checklist

- [x] **Spec coverage:** html parameter ✓ · welcome_email template ✓ · config fields ✓ · create_key email call ✓ · resend endpoint ✓ · CreateUser confirmation ✓ · Users resend button ✓ · NOTES homework ✓ · gcloud commands ✓
- [x] **No placeholders:** all code blocks are complete
- [x] **Type consistency:** `send_email(html=...)` matches Task 1 signature · `welcome_email(slug=, key=, service_url=, email_support=)` consistent across Tasks 2 and 4 · `_FakeSettings.service_url` / `.email_support` added in Task 3 before used in Task 4 · `resendInvite` in api.ts matches endpoint `POST /admin/keys/{slug}/email`
