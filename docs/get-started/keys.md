# Get Your Keys

A researcher reading this page can collect every credential SciAgent uses in under 15 minutes.
You only need the **Required** ones to start.

!!! tip "Using the hosted demo? You only need a Zotero key."
    The public backend at `https://sciagent-ewpafdgfya-ew.a.run.app` runs its own LLM
    (DeepSeek, operator-paid). You do **not** need an LLM provider key — skip straight to
    the Zotero API Key section below.
    The LLM section applies only if you are running your own backend or want to override
    the operator's key with your own.

---

## LLM Provider Key — Required for self-hosted / optional for hosted demo

When running your own backend, SciAgent requires exactly one LLM provider key to generate
search plans and rerank results. If `AGT_LLM_PROVIDER` is unset, the runtime auto-detects
a provider from whichever key is present (OpenAI → Anthropic → xAI → Groq).
When using the hosted demo, you can optionally supply your own key via **Preferences →
LLM Override** in the add-on to charge your account instead of the operator's.

The first-run card in the add-on auto-detects the provider from the key prefix:
`sk-ant-` → Anthropic · `xai-` → xAI · `gsk_` → Groq · `sk-` → OpenAI.

### OpenAI

**Who needs it:** anyone using GPT models (default provider).

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Click **Create new secret key**.
3. Copy the key — it starts with `sk-`.

**Environment variable:** `AGT_OPENAI_API_KEY`

**Sidebar field:** Preferences → SciAgent → LLM Provider → OpenAI API Key

### Anthropic

**Who needs it:** anyone using Claude models.

1. Go to [console.anthropic.com/account/keys](https://console.anthropic.com/account/keys).
2. Click **Create Key**.
3. Copy the key — it starts with `sk-ant-`.

**Environment variable:** `AGT_ANTHROPIC_API_KEY`

**Sidebar field:** Preferences → SciAgent → LLM Provider → Anthropic API Key

### xAI / Grok

**Who needs it:** anyone using Grok models.

1. Go to [console.x.ai](https://console.x.ai).
2. Navigate to **API Keys** and create a new key.
3. Copy the key — it starts with `xai-`.

**Environment variable:** `AGT_XAI_API_KEY`

**Sidebar field:** Preferences → SciAgent → LLM Provider → xAI API Key

### Groq

**Who needs it:** anyone wanting fast, free-tier inference on open models.

1. Go to [console.groq.com/keys](https://console.groq.com/keys).
2. Click **Create API Key**.
3. Copy the key — it starts with `gsk_`.

**Environment variable:** `AGT_GROQ_API_KEY`

**Sidebar field:** Preferences → SciAgent → LLM Provider → Groq API Key

### Ollama (local, free)

**Who needs it:** anyone who wants fully offline inference with no API costs.

No key required. Install Ollama from [ollama.com](https://ollama.com), then run:

```bash
ollama pull llama3.2
```

Set the following in your `.env`:

```bash
AGT_LLM_PROVIDER=ollama
AGT_LLM_MODEL=llama3.2
```

No sidebar key field is needed — the backend connects to the local Ollama server directly.

### OpenAI-compatible endpoint (DeepSeek, Together AI, LM Studio, etc.)

**Who needs it:** anyone routing requests through a custom or third-party OpenAI-compatible API.

Set the following in your `.env`:

```bash
AGT_LLM_PROVIDER=openai-compatible
AGT_LLM_BASE_URL=https://api.deepseek.com/v1
AGT_LLM_API_KEY=your-key-here
AGT_LLM_MODEL=deepseek-chat
```

Replace `AGT_LLM_BASE_URL` and `AGT_LLM_MODEL` with values from your provider's documentation.

---

## Zotero API Key — Required for library writes

**Who needs it:** anyone who wants SciAgent to save papers into their Zotero library.

**Why:** Zotero's write API requires authentication. Without this key, search works but
nothing can be approved into your library.

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys).
2. Click **New Key**.
3. Check **Allow write access** (read access is pre-checked).
4. Click **Save Key**.
5. Copy the 32-character hex key string.

Your numeric **User ID** is shown at the top of the same page (e.g. `1234567`).

| Variable | Value |
| -------- | ----- |
| `AGT_ZOTERO_API_KEY` | the 32-character key string |
| `AGT_ZOTERO_LIBRARY_ID` | your numeric User ID |
| `AGT_ZOTERO_LIBRARY_TYPE` | `user` for a personal library (default); `group` for a shared group |

---

## Optional Academic Keys — Optional (improve results, not required)

All providers below work without a key at reduced rate limits. Adding a key raises those limits
and, in some cases, unlocks additional data fields.

### Semantic Scholar

**Variable:** `AGT_SEMANTIC_SCHOLAR_API_KEY`

The free tier works without a key but is throttled. A key unlocks higher rate limits and
priority access to bulk endpoints.

1. Go to [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api).
2. Click **Get an API Key** and complete registration.
3. Copy the key from your dashboard.

### NCBI / PubMed

**Variable:** `AGT_NCBI_API_KEY`

Without a key, NCBI allows 3 requests per second. A key raises that to 10 requests per second,
which significantly speeds up deep searches that hit PubMed.

1. Go to [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) and sign in or create an account.
2. Open **API Key Management** from your account settings.
3. Click **Create an API key** and copy the result.

### CORE

**Variable:** `AGT_CORE_API_KEY`

CORE provides access to millions of open-access full-text records. Free registration.

1. Go to [core.ac.uk/services/api](https://core.ac.uk/services/api).
2. Register for a free API key.
3. Copy the key from the confirmation email or your dashboard.

### SerpAPI (Google Scholar)

**Variable:** `AGT_SERPAPI_KEY`

SerpAPI is the only provider that surfaces Google Scholar results. A paid plan is required.

1. Go to [serpapi.com](https://serpapi.com) and sign up.
2. Navigate to **Dashboard → API Key**.
3. Copy the key string.

### Dimensions

**Variable:** `AGT_DIMENSIONS_KEY`

Dimensions offers broad coverage of grants, clinical trials, and publications. Access requires
either institutional affiliation or a verified researcher account on the free tier.

1. Go to [dimensions.ai](https://www.dimensions.ai) and request access.
2. Once approved, locate your API key in the developer settings.
3. Copy the key string.

---

## Polite Pool Email — Strongly recommended

**Variable:** `AGT_MAILTO=your-email@example.com`

This is not a key — just your email address. OpenAlex, Crossref, and DOAJ use it to route
your requests into their polite pool, which gives you higher rate limits and lower latency.
These providers use the address to contact you if your usage is abnormal; it is never used
for marketing.

Add it to your `.env`:

```bash
AGT_MAILTO=your-email@example.com
```

---

## Next Steps

- [Advanced Config](../power-user/advanced-config.md) — full list of `AGT_*` environment variables, proxy
  settings, timeouts, disabled providers, PDF attachment, and backend security options.
- [User Manual](user-manual.md) — how to run searches, approve results, and use filters.
