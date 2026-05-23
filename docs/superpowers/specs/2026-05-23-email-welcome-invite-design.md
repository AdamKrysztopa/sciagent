# Email: Welcome Email & Admin Invite System

**Date:** 2026-05-23
**Status:** Approved for implementation

## Overview

Wire the existing email infrastructure (Resend API, `email.py`, `email_api_key` config) to send
a formatted HTML welcome email when an admin creates a new user. The Messages page email channel
becomes functional as a side-effect of the same infrastructure setup. A "Resend invite" button
on the Users page allows re-sending the welcome email to existing users.

## Goals

- Admin creates a user → user receives a well-formatted HTML welcome email with their API key
- Messages page "Email only" / "Banner + Email" channels work in production
- Admin can resend a welcome email to any existing user from the Users table
- All email credential management happens via GCP Secret Manager + gcloud commands (no manual
  file editing on the server)

## Non-Goals

- PDF manual / user guide (future work; template includes a placeholder)
- SendGrid or SMTP alternative (Resend is the chosen provider)
- Email open/click tracking
- Email scheduling or queuing

---

## Section 1 — Infrastructure

### Resend setup (one-time manual steps)

1. Sign up at <https://resend.com> and create an API key (name it `sciagent-production`)
2. Add domain `mechai.pl` in the Resend dashboard → Domains → Add Domain
3. Resend provides 3 DNS TXT records; add them in Google Workspace Admin → Domains → DNS records
4. Wait ~5 minutes for verification to complete
5. Confirm the domain shows **Verified** in Resend

### GCP wiring (gcloud commands — run once)

```bash
PROJECT=sciagent-496617
SA=sciagent-backend@sciagent-496617.iam.gserviceaccount.com
REGION=europe-west1

# 1. Create the secret
gcloud secrets create agt-email-api-key \
  --replication-policy=automatic \
  --project=$PROJECT

# 2. Populate it (replace re_YOUR_KEY with the actual Resend API key)
echo -n "re_YOUR_KEY" | gcloud secrets versions add agt-email-api-key \
  --data-file=- \
  --project=$PROJECT

# 3. Grant the backend service account read access
gcloud secrets add-iam-policy-binding agt-email-api-key \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT

# 4. Wire env vars into the Cloud Run revision
gcloud run services update sciagent \
  --update-env-vars="AGT_EMAIL_API_KEY=re_YOUR_KEY,AGT_EMAIL_FROM=sciagent@mechai.pl" \
  --region=$REGION \
  --project=$PROJECT
```

> **Note:** The email API key is passed as a plain env var (same pattern as the existing config).
> It is also stored in Secret Manager for auditability and rotation. The Cloud Run env var is
> the live value; update it when rotating the key.

---

## Section 2 — Backend Changes

### `src/agt/email.py` — HTML support

Add an optional `html: str | None = None` parameter to `send_email()`. When provided, include
it in the Resend payload so the email client renders the HTML version with the plain-text as
fallback. No new dependencies.

### `src/agt/email_templates.py` — new module

A single public function:

```python
def welcome_email(
    slug: str,
    key: str,
    service_url: str,
    support_email: str,
) -> tuple[str, str, str]:  # (subject, text, html)
```

**Subject:** `Welcome to SciAgent — your API key is ready`

**HTML template sections:**
1. SciAgent header (name + tagline, no external image dependency)
2. Greeting: "Hi {slug},"
3. API key in a styled `<code>` block with a copy hint
4. 3-step getting started:
   - Install the Zotero addon
   - Open Zotero → SciAgent sidebar
   - Paste your API key
5. Service URL link
6. "Full user manual coming soon" note
7. Support footer: reply to `{support_email}`

**Plain-text version:** Same content, no HTML tags, API key on its own line.

### `src/agt/api/admin.py` — welcome email on create

In `create_key`, after `registry.update(users)` succeeds, fire `send_email()` with the welcome
template. Email errors are caught, logged at `warning` level, and do **not** propagate — the
HTTP 201 response is returned regardless. This prevents a flaky email provider from blocking
user provisioning.

```python
try:
    subject, text, html = welcome_email(body.slug, key, settings.service_url, settings.email_support)
    await send_email(api_key=email_key, from_address=settings.email_from,
                     to=[entry.email], subject=subject, text=text, html=html)
except Exception:
    _log.warning("welcome_email_failed", slug=body.slug)
```

### `src/agt/api/admin.py` — resend invite endpoint

New endpoint: `POST /admin/keys/{slug}/email`

- Looks up the user in the registry (404 if not found)
- Re-sends the welcome email using the same template
- Returns `{"status": "sent", "slug": slug}`
- Same error-suppression pattern as create: email failure → logged, not propagated

### `src/agt/config.py` — two new optional fields

```python
service_url: str = Field(
    default="https://sciagent-ewpafdgfya-ew.a.run.app",
    alias="AGT_SERVICE_URL",
    description="Public service URL included in welcome emails.",
)
email_support: str = Field(
    default="krysztopa@gmail.com",
    alias="AGT_EMAIL_SUPPORT",
    description="Support email address shown in welcome emails.",
)
```

Both have sensible defaults so no env var change is required immediately.

---

## Section 3 — Frontend Changes

### `admin-panel/src/api.ts`

Add one method:

```ts
resendInvite: (apiKey: string, slug: string) =>
  apiFetch<{ status: string }>(`/admin/keys/${slug}/email`, apiKey, { method: "POST" })
```

### `admin-panel/src/pages/CreateUser.tsx`

In the success state (after a user is created), display below the key:

> Email sent to `{email}` — they'll receive their API key and getting-started instructions.

No API change needed; the email address is already in the `CreateKeyResponse`.

### `admin-panel/src/pages/Users.tsx`

Each row in the users table gets a **"Resend invite"** action button alongside the existing
Revoke button. Clicking it:

1. Calls `api.resendInvite(apiKey, slug)`
2. Shows inline "Sent!" text for 2 seconds, then resets
3. On error, shows inline error text

---

## Data Flow

```
Admin fills CreateUser form
  → POST /admin/keys
    → write to GCP Secret Manager
    → call send_email() [fire-and-forget, errors logged]
      → POST https://api.resend.com/emails
        → Resend delivers to user's inbox
  → 201 response with { slug, key, email, budget_usd }
    → CreateUser.tsx shows key + "Email sent to {email}"
```

---

## Invariants

- Email failure never fails user creation (catch-and-log pattern)
- `send_email()` is a no-op when `api_key` is empty (existing behaviour preserved)
- No new runtime dependencies added to the core package
- All new config fields have defaults → zero breaking change to existing deployments
- `pyright` must pass at zero errors on all changed files

---

## Testing

- `email_templates.py`: unit test that `welcome_email()` returns non-empty subject/text/html
  and that the key appears in both text and html outputs
- `admin.py` create endpoint: existing VCR tests remain green; add a test that asserts email
  send is attempted (mock `send_email`) and that a send failure does not affect the 201 response
- `email.py`: existing no-op test (empty api_key → no HTTP call) remains; add test for html
  parameter being included in the payload

---

## Files Changed

| File | Change |
|---|---|
| `src/agt/email.py` | Add `html` parameter |
| `src/agt/email_templates.py` | New — welcome email template |
| `src/agt/api/admin.py` | Call welcome email in create_key; add resend endpoint |
| `src/agt/config.py` | Add `service_url` and `email_support` fields |
| `admin-panel/src/api.ts` | Add `resendInvite` method |
| `admin-panel/src/pages/CreateUser.tsx` | Show "email sent" confirmation |
| `admin-panel/src/pages/Users.tsx` | Add "Resend invite" button per row |
| `NOTES.local.md` | Document email secret + gcloud commands |
| `docs/superpowers/specs/2026-05-23-email-welcome-invite-design.md` | This file |
