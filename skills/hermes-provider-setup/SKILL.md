---
name: hermes-provider-setup
description: Set up Hermes providers, keys, rate limits and model slots.
version: 0.9.1
author: Hermes Agent
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  scope: standalone
  hermes:
    category: personal
    tags:
    - hermes
    - provider
    - config
    - credential-pool
    - rate-limit
    related_skills:
    - xai-provider
    - artificial-analysis-cli
---
# Hermes Provider Setup

Class-level reference for the **mechanics** of provider setup in Hermes. This skill is NOT for individual provider quirks (those live in `xai-provider`, `openai-codex-provider`, etc.) and NOT for per-task auxiliary routing (that is the `auxiliary:` slot layer, covered below in "Auxiliary (side-task) model slots"). It covers the **shared machinery**: config schema, credential pool, rate-limit handling, and the built-in provider landscape.

## When This Skill Activates

- User wants to add a new provider and asks "where in config.yaml does that go?"
- User has multiple API keys for one endpoint (failover, quota separation, work vs personal)
- User hits 429 rate limits and wants to know what knobs exist
- User asks "what's the difference between providers: and custom_providers:?"
- User asks about the three api_mode values (chat_completions, codex_responses, anthropic_messages)
- User wants one step — a review, a second opinion — to run on a *different* (stronger) model than the session, or asks how to pin a model for a single run
- User asks whether model or provider can be changed mid-session, or which credential of a pool gets used first
- User asks *which* model belongs in *which* slot on a plan he already pays for (make routing smarter, pick a model per purpose) — see `references/model-selection-workflow.md`
- User asks whether the subscription is still enough, where the monthly quota went, or whether to upgrade a plan tier — attribute the burn before recommending money (see "Subscription Adequacy" below)
- User asks whether speech input / dictation works, where a dictated message is actually transcribed, or why a voice feature leaves no trace in the server logs
- User asks what Hermes actually puts on the wire for a provider — whether a configured field (reasoning effort, thinking flag, `extra_body` key) reaches the endpoint — or why the API ignores a parameter Hermes seems to send
- User asks whether a provider-specific reasoning/thinking level (anything outside `low|medium|high`) can be made to reach the API

## Config Schema: `providers:` vs `custom_providers:`

Hermes has TWO ways to register a non-built-in provider, and they are NOT redundant:

| Field | Schema | Best for |
|---|---|---|
| `providers:` | Dict, key = provider name | **New setups** — unique keys prevent duplicates, schema-validated on save. The code calls this the v12+ keyed form |
| `custom_providers:` | List, each entry carries a `name:` field | Backwards compatibility for configs written before the keyed form |

**One list-shaped view.** `get_compatible_custom_providers()` (`hermes_cli/config_providers.py`) normalizes both forms into a single internal list — keyed entries are converted to the legacy shape and deduplicated by `provider_key`, else by `(name, base_url, model)`. That view is never materialised back into `config.yaml`; writing it there would duplicate entries in the UIs.

**Decision rule:** for a new provider write `providers:` (keyed dict). Leave `custom_providers:` alone unless you are migrating an old config — and never describe the same provider in both blocks.

### Minimal `providers:` example

```yaml
providers:
  my_provider:
    name: "My provider"
    base_url: "https://api.example.com/v1"
    api_mode: "chat_completions"   # chat_completions | codex_responses | anthropic_messages
    key_env: "MY_PROVIDER_KEY"     # preferred over an inline api_key
    models:
      some-model: {}
```

Two endpoints of the same family (two regions, two accounts) are two entries. `models:` names what that endpoint serves — deployment names behind a gateway, model IDs behind an OpenAI-compatible API.

**Valid fields** (`hermes_cli/config.py:_VALID_CUSTOM_PROVIDER_FIELDS`):
`name`, `base_url`, `api_key`, `api_mode`, `model`, `models`, `context_length`, `rate_limit_delay`, `extra_body`, `ssl_ca_cert`, `ssl_verify`, `catalog_provider`, `key_env`.

**Common mistakes:**
- `providers:` is a **dict**, not a list → YAML uses `key: value`, never `-` bullets.
- `providers: {}` (empty dict) is valid; `providers: null` is NOT (use `{}` or omit).
- A malformed `custom_providers` (a string or a dict instead of a list) no longer empties the whole view silently: the legacy entries are skipped with a warning and a "change to:" hint, while any `providers:` entries stay in effect. A provider that "disappeared" from a picker is usually this shape error.

### Headless registration (no TTY for the model picker)

`hermes model` is interactive. Register a custom provider without it — one `hermes config set` per field merges into the existing `providers:` dict (and is the supported writer for config.yaml, which `patch()` refuses as security-sensitive):

```bash
hermes config set providers.<key>.name "<Display Name>"
hermes config set providers.<key>.base_url "https://api.example.com/v1"
hermes config set providers.<key>.api_mode "chat_completions"
hermes config set providers.<key>.key_env "<KEY_ENV_NAME>"
hermes config set providers.<key>.context_length <from live /models>
hermes config set 'providers.<key>.models' '{"<model-id>": {}}'   # JSON string, parsed into the dict
```

Then `hermes config get providers` to confirm the merge (an existing sibling entry survives), `hermes config check` to validate, and a probe (`hermes -z "..." --provider <key> -m <model-id>`, then again with `-t file`) before touching `model.default` — a configured provider is not a working one. Before naming `<key>`, grep the install for the name: a key that matches a built-in provider (see the transport table below) shadows or collides with it.

## Credential Pool with Multiple Keys

When you have multiple credentials for one provider (failover, quota separation, work vs personal), Hermes has a **pool mechanism** (`credential_pool` in `~/.hermes/auth.json`) plus a **strategy** (`credential_pool_strategies.<provider>` in `config.yaml`).

### Register multiple credentials

```bash
# Same provider, two distinct keys, each with a label
hermes auth add opencode-go --type api-key --label "primary"   --api-key "KEY_A"
hermes auth add opencode-go --type api-key --label "secondary" --api-key "KEY_B" --priority 1

# Verify the pool (index, label, type)
hermes auth list opencode-go
```

`--priority N` places a new credential (0 = tried first under `fill_first`); without it the entry appends last. `hermes auth priority <provider> <index|id|label> <N>` reorders afterwards and renumbers the others — the label is how a credential is named in `list`, `remove` and `priority`.

### Strategy, and when a second key is worth it

`credential_pool_strategies.<provider>` is per provider, never global: `fill_first` (the default — first key until it is exhausted, then the next), `round_robin`, `least_used`, `random`. It is an ordinary config key (edit `config.yaml` / `hermes config set`); there is **no** `hermes auth pool` command — `hermes auth` offers `add`, `list`, `remove`, `reset`, `priority`, `refresh`, `status`, `logout`, `upgrade`, `spotify`.

A second key is worth the bookkeeping for **failover** (A drains, B takes over) or for **separating purposes** (work vs private, separate rate-limit buckets; labels keep them apart in `auth list`). Whether it adds usable room depends on whether the limit that binds you is per key or per account — read that, do not assume a second key doubles the allowance.

### One key belongs in `.env`; the pool only mirrors it

Every built-in provider declares its env var (`hermes_cli/auth.py`, e.g. `("opencode-go", …, ("OPENCODE_GO_API_KEY",))`). `.env`-seeded pool rows are **borrowed**: `auth.json` keeps label, `source: env:<VAR>` and a `secret_fingerprint`, never the value. A `source: manual` row (what a GUI "paste key into the pool" flow writes) stores the plaintext `access_token` in `auth.json` instead. So the single-key default is `.env` + `key_env`, and the pool is for the *second* key.

**Moving a `manual` row back into `.env` — order matters:**

1. Append the value from `auth.json` to `~/.hermes/.env` as `<PROVIDER>_API_KEY=…` (never echo it; the desktop's own path is Settings → Environment / `config_env.py` → `save_provider_env_credential()`, which writes `.env`, lifts any suppression and re-runs `load_pool()`).
2. Only then `hermes auth remove <provider> <manual-id>` — a `manual` source has no external cleanup step, so the row drops and the plaintext copy is gone.
3. **Never `auth remove` an `env:<VAR>` row to "clean up"**: `_remove_env_source()` deletes the variable from `.env` *and* records `suppressed_sources.<provider>` so the source is never re-seeded, even if the var comes back. The desired end state is the opposite — the env row staying, with `secret_fingerprint` matching the live value.

Verify the move with fingerprints, not the key: `sha256:<value>[:16]` must equal the row's `secret_fingerprint` (`agent/credential_persistence.py:fingerprint_secret_value`), `hermes auth list <provider>` must show one `env:` row and no secret on disk, then probe with `hermes -z`.

## Rate-Limit 429 Handling

Hermes has three knobs that interact. Don't just add retries — understand the cause first.

### Knob 1: `api_max_retries` (transient errors)

```yaml
agent:
  api_max_retries: 5        # default 3; higher = more aggressive retry
```

**What it covers:** network timeouts, transient 5xx, 429 with `Retry-After` header.

**What it does NOT cover:** 401 (re-auth needed), permanent 403 (escalate), 404 (wrong model name).

### Knob 2: `max_concurrent_sessions` (self-throttling)

```yaml
max_concurrent_sessions: 1        # default null = unlimited
```

**Effect:** Serializes all sessions, so you never burst past your quota.

**Trade-off:** Subagents / cron jobs that run in parallel will queue.

### Knob 3: `fallback_providers` (provider failover)

```yaml
fallback_providers:
  - {provider: opencode-go, model: <cheap-model>}    # first fallback
  - {provider: opencode-go, model: <strong-model>}   # same provider, another model = a tier step
  - {provider: xai-oauth,   model: <model>}          # another provider
```

**Every entry must be a dict carrying BOTH `provider` and `model`.** A bare provider list (`fallback_providers: [opencode-go]`) resolves to **zero entries** — the config resolver and the agent's chain initializer both skip anything that is not a dict with both keys — so the chain sits in the file, looks configured, and never fires. `hermes fallback list` is the authoritative check (it prints "No fallback providers configured." for the bare list, even while the YAML looks populated); never infer an armed chain from the YAML. `hermes fallback add` is the picker and needs a TTY; headless, write the dicts with `hermes config set fallback_providers '[{"provider": "…", "model": "…"}]'`, which parses the JSON into real entries.

**Effect:** when the primary returns 429 OR an auth failure, Hermes tries the next entry, in the order written. Same provider with a different model is a legal entry (that is the cheap→strong step); only an entry identical to the primary route is refused. Entries deduplicate by `(provider, model, base_url)`. `fallback.min_switch_reset_seconds` (default 0 = off) keeps a turn on a rate-limited primary when its declared reset is imminent, instead of switching away for a single call.

### Diagnostic sequence when you see 429

1. **Check provider quota** — is this your quota or a per-IP/per-model limit?
2. **Lower concurrency** — set `max_concurrent_sessions: 1`.
3. **Add fallback** — extend the chain with dict entries; `hermes fallback list` tells you whether it is actually armed.
4. **Switch model** — sometimes a smaller model (e.g. `grok-3-mini` vs `grok-4.3`) has its own quota bucket.
5. **Only then** consider raising `api_max_retries` — high retries against a hard quota is just slow failure.

## Live Provider Inventory and Quota (probe the endpoint, not the docs)

Docs describe a curated picture; the provider's own API describes the state. Before answering "which models does my plan include", "what does this model cost here", or "how much quota is left", read it from the configured `base_url`:

```bash
# BASE_URL = model.base_url from config.yaml; KEY name = <PROVIDER_UPPER_SNAKE>_API_KEY in ~/.hermes/.env
curl -sS "$BASE_URL/models" -H "Authorization: Bearer ***" | jq -r '.data[].id' | sort
curl -sS "$BASE_URL/usage"  -H "Authorization: Bearer ***" | jq .   # windowed quota, where offered
```

Rules that survive the next docs update:

- **`/models` often answers without a key — fine for early reconnaissance, but not a plan inventory.** The unauthenticated answer can be the provider's **public catalogue**, a superset carrying IDs the plan rejects at request time. Plan membership comes from the **keyed** call (`Authorization: Bearer <key>`) — quote that list for config decisions, report the delta to the public catalogue in both directions, and take `context_length`, max output and per-token prices from the keyed response where offered. A `pricing` value of `0` is the catalogue's silence (unpublished), not free.
- **A vendor's integration page for your exact tool names the values to plug in** (base URL, api_mode, model id, context length) and is often newer than the vendor's pricing page — but treat it as the second-best source and confirm every value against live `/models`.
- **Diff the live IDs against the published list and report the delta in both directions.** Curated pages lag: a live-only model exists, and a documented model can already be retired.
- A model with no documented cap has an **unknown** cap — not zero, not unlimited.
- **OpenCode's relay rejects bare chat calls.** `POST /chat/completions` on `opencode.ai/zen…` returns `400 MissingSessionID` without an `x-opencode-session` header; Hermes adds it on every OpenCode target (conversation key, else an ephemeral `oneshot-<hex>` — `agent/opencode_affinity.py`). A hand-rolled `curl` that omits it produces a false "provider broken" finding: probe `/models` (200 = auth fine) or go through `hermes -z`, and add the header if you must hit chat directly.
- Window caps (rolling ≈5 h / weekly / monthly) and per-model dollar caps are two layers that both apply; plan tiers are **not** constant multiples of each other, so never derive one tier's column from the other — and some plans have only one tier (OpenCode Go is not one of them: Go $10 → Go Plus $40, per-model caps growing 2×–8× — `references/opencode-go-plan.md`).
- Quote the fetch time with the numbers, and re-fetch rather than re-citing an earlier run.

See `references/live-provider-probes.md` for the key-loading one-liner (the value never enters the transcript), endpoint response shapes, and the credential-visibility chain.

## Wire Probes: What Hermes Actually Sends

The transport code shows what it *can* send; only a captured request shows what it *does*. To answer "does Hermes put field X on the wire for provider Y", register a throwaway `providers.<tmp>` entry whose `base_url` points at `scripts/wire-echo-server.py` on localhost, run `hermes -z` against it, and read the logged body — then remove the entry and kill the server by recorded PID. No endpoint traffic, no guessing from code paths.

Verified wiring facts for `providers:` entries (top-level `reasoning_effort` tracking `agent.reasoning_effort`; off-ladder levels silently degrading to `medium` on the global knob but passing **verbatim** through the per-model dict `agent.reasoning_overrides.<model>: {enabled: true, effort: <level>}` — which keeps session `/reasoning` live, unlike the `extra_body` pin that overrides the knob and disables `/reasoning`) plus the per-level impact probe (`reasoning_tokens` in the usage block): `references/request-wire-probes.md`.

## Subscription Adequacy: Attribute the Burn Before Recommending an Upgrade

Question class: "is my plan still enough?", "my monthly quota is nearly gone — should I upgrade?", "where did the allowance go?". `/usage` percentages say *that* the plan is draining, never *why* and never which bucket. No money advice before the attribution step:

1. **Place the cycle.** `/usage` gives `percent` + `resetsAt` per window; cycle start = `resetsAt` minus the window length. Report "N % at D days into the cycle" and the linear projection of the day it reaches 100 % — labelled as a projection, not a promise.
2. **Attribute the burn from the local ledger.** `state.db`'s `session_model_usage` records what each model actually spent (`scripts/attribute-provider-burn.py --since <cycle start>`; schema, recipe and price math: `references/live-provider-probes.md` § 6). Plan providers report `estimated_cost_usd = 0`, so price the tokens from the plan's own rows (in / out / cached read per 1M) and name the peak/off-peak basis.
3. **Name the binding bucket.** Map the burn onto the per-model caps. "One model carries ~95 % of the burn" is the actionable sentence; only touch slot routing when several buckets are hot.
4. **Offer capacity in this order:**
   1. **Redirect to a direct provider key** that serves the same model at the plan's off-peak rate — pay per token, no fixed cost, exactly the bucket that binds. Wire it as a `fallback_providers` dict entry carrying both `provider` and `model` (Knob 3 above) so it fires without a manual switch.
   2. **Balance overflow** ("Use balance") as a bridge for days only — billed at the plan's **peak** row, typically 2× the off-peak rate.
   3. **Tier upgrade** only after a *second* consecutive cycle breaches the same bucket: a recurring cost against what may be a one-time overage.
5. **Give one recommendation plus its reversal trigger** ("upgrade if the next cycle breaches again"), not a menu of options.

Traps specific to this procedure:

- **Overflow prices track the peak row.** The pay-per-token catalogue lists DeepSeek V4.1 Flash at $0.30/$1.20 — the Go peak price, twice the off-peak plan rate. Compare overflow against the row you would actually pay, or the recommendation flips.
- **The same model under another slug is not another model.** `deepseek-flash` on a direct API is `deepseek-v4.1-flash` on the plan. Before buying headroom, check whether the "fallback" already provides it pay-per-token.
- **A zero cost column is the catalogue's silence.** `estimated_cost_usd = 0` for a plan provider means "no price known", not "free" — recompute from the plan's price rows or say you cannot.

## Provider Keys: Which Consumer Sees Which Key

A key that works inside Hermes can be invisible to a shell command, and vice versa. Three consumers, three rules:

| Consumer | How it gets the key | Restart / reload needed? |
|---|---|---|
| Hermes itself (model calls, tools, skill readiness, MCP) | per-turn secret scope built from `~/.hermes/.env` + hydrated sources | no — a new `.env` entry is live on the next turn |
| A bare `os.environ` reader (boot-time config, a child spawned from a copy of the process env) | `load_hermes_dotenv()` at process start only | `/reload` (CLI, or the `reload.env` RPC used by the TUI/desktop) |
| External CLI / shell command run from the terminal tool | the terminal shell env: exported in `~/.bashrc` (sourced because `terminal.auto_source_bashrc: true`), or declared in `terminal.env_passthrough` | no |

`terminal.env_passthrough` in `config.yaml` is the supported route for a **non-Hermes** key into `terminal` / `execute_code` children: the declared names resolve through the secret scope, so they are fresh from `.env`. Hermes-managed provider credentials are refused there on purpose (credential scrubbing) — a shell `export` in `~/.bashrc` is the route for those when a CLI needs them.

## Built-in Providers (the 20+ landscape)

Hermes has **~20 built-in providers** that don't require `providers:` config — they're discovered via `models.dev` and registered in `HERMES_OVERLAYS` (`hermes_cli/providers.py`).

### Provider categories by transport

| Transport | Providers | Notes |
|---|---|---|
| `openai_chat` (default) | openrouter, nous, lmstudio, qwen-oauth, ollama-cloud, kimi-coding, opencode-zen, opencode-go | Most common; OpenAI-compatible chat completions |
| `codex_responses` | openai-codex, openai-api, xai-oauth, xai, copilot-acp | OpenAI Responses API (`/v1/responses`) — not just for Codex |
| `anthropic_messages` | any Claude endpoint configured with that `api_mode` | Anthropic Messages API (`/v1/messages`) |
| `bedrock_converse` | bedrock | AWS Bedrock |
| `virtual` | moa | Mixture-of-Agents local router |

### Quick provider-selection heuristic

1. **Daily driver / quality:** whatever your subscription tier gives (xai-oauth for Premium+, openai-codex for ChatGPT Pro).
2. **Cheap fallback:** `opencode-go`.
3. **Local / private:** `lmstudio`, `ollama-cloud`.
4. **Aggregator:** `openrouter` (400+ models behind one key).

## Which Knob Decides Which Model: Session, Subagent, One-Shot

Three separate knobs, easy to confuse:

| Scope | Config key | Controls |
|---|---|---|
| Session / main thread | `model.default` + `model.provider` | the model you are talking to; also the default for `hermes -z` unless overridden |
| Subagents | `delegation.model` + `delegation.provider` | what **every** `delegate_task` child inherits — no per-child override exists in the tool schema |
| One run | `hermes -z "<prompt>" --provider <P> -m <M> -t <toolsets>` | that invocation only: fresh context, own session, own tool grants |

Read the value before quoting it (`hermes config get delegation.model`) — the model picker and other sessions write these keys, so a value read earlier in the day can already be stale.

**These three knobs are not the whole inventory.** Exactly five more top-level config sections carry model choices: `tts`, `stt`, `x_search`, `moa`, `smart_model_routing`. An audit of "every place a model is configured" — or a cleanup after removing a provider — must cover the three layers **plus** those five, and `tts`/`stt` are whole subsystems with per-provider subkeys, so a single top-level grep is not an audit. What each of the five routes: `references/model-routing-slots.md`.

**Review independence.** Every `delegate_task` child inherits `delegation.model`, so an implementer and a reviewer on the delegation rail share the same blind spots. Either keep `delegation.*` on the cheap model and run each review as a pinned one-shot, or use the native `review` slot instead of hand-rolling one. **Probe before building on a model:** the list in `provider_models_cache.json` is a catalogue, not a credential check — first ask the model to answer, then ask it to read a file with `-t file`.

Commands, the one-shot recipe and what a failed probe names verbatim: `references/model-routing-slots.md`.

## Auxiliary (side-task) model slots

Side tasks route through their own slots under `auxiliary:` in `config.yaml` — the third layer next to `model.*` (session) and `delegation.*` (subagents). `hermes model` → "Configure auxiliary models" writes them; read one back with `hermes config get auxiliary.<slot>` (`hermes config get auxiliary.review`). `/review` runs on `auxiliary.review` when set, else on the parent's credentials, and cannot be triggered by the agent.

Full slot table (18 slots, incl. `approval`, `triage_specifier`, `kanban_decomposer`, `skills_hub`, `mcp`), the field list, the timeout defaults and the `/review` mechanics: `references/model-routing-slots.md`. Reasoning per aux slot is wire wiring, not a knob: the slot's `reasoning_effort` folds into nested `reasoning`, while off-ladder provider levels and top-level `reasoning_effort` need the slot's `extra_body` — `references/request-wire-probes.md`.

**Trust boundary per slot is binary — trusted / untrusted, not a scale.** A compliance context does not accept a privacy gradient; a slot either may see parent-context content or it may not. Two questions per slot: **what exactly does the aux model see** (name the fields, not the category — `tts_audio_tags` receives the **text** of the last assistant turn, not audio), and **can it pull more content itself** (`curator` carries `skill_view` and can load full skill bodies)? Defaults: `web_extract` / `mcp` are often untrusted-OK (URLs and tool definitions are external by definition); `vision`, `approval`, `title_generation`, `monitor`, `tts_audio_tags`, `compression`, `background_review`, `curator` are trusted (commands, first messages, full history and skill bodies can all carry internal content); `skills_hub` / `profile_describer` are trusted whenever skill names or descriptions can carry internal project names. When unsure, default to **trusted** (= parent credentials) — worst-case-denial is the cheaper error. Before giving aux-routing advice in a compliance-relevant context, grep the profile's own skills for internal names first (a self-audit step).

## Pitfalls

### Pitfall 1 — `providers:` and `custom_providers:` are NOT redundant

Both are normalized into one internal list, and the dedupe only catches an identical `provider_key`, or an identical `(name, base_url, model)` triple. Two entries for the same endpoint under different spellings therefore both survive and drift apart. **Pick one format per provider.**

### Pitfall 2 — `auth add` is not idempotent

Running `hermes auth add xai-oauth` twice creates TWO pool entries (different IDs, same label if you provide one). Use `hermes auth list <provider>` to verify before re-adding. Use `hermes auth remove <provider> <index|id|label>` to clean up duplicates.

### Pitfall 3 — Pool strategy is per-provider, not global

`credential_pool_strategies` is a dict keyed by provider name:

```yaml
credential_pool_strategies:
  opencode-go: fill_first
  xai-oauth: round_robin
  openai-codex: fill_first
```

If you have multiple providers with multiple keys each, set strategy **for each** independently.

### Pitfall 4 — `api_max_retries` doesn't help against hard quota limits

If your provider returns 429 with NO `Retry-After` header (some do), retries don't help — they just spam the quota check. The same holds for the deterministic refusals Hermes deliberately does not retry (402 exhausted balance, content-policy blocks): a retry cannot succeed there. **Reduce concurrency first, then add retry budget.**

### Pitfall 5 — Model and provider ARE switchable mid-session

`/model <model> --provider <provider>` re-points the running session (CLI, TUI, gateway, Telegram); `--provider` is the only way to name a provider, because a colon is reserved for OpenRouter variant suffixes (`:free`). Without `--global` the change is session-scoped — the next session starts from `config.yaml` again — and a switch re-resolves credentials, `base_url` and `api_mode` for the new provider.

What launch flags do NOT do: `hermes --provider X --model Y` configures that invocation; it cannot retarget a session that is already running. Open a fresh session (`/new`) when you want both a new route and a clean context.

### Pitfall 6 — `key_env` vs `api_key` in `providers:`

```yaml
providers:
  my_provider:
    base_url: "https://api.example.com"
    key_env: "MY_PROVIDER_KEY"   # reads from .env at runtime — preferred for secrets
    api_key: "literal-string"     # inline — only for dev/testing
```

**Always use `key_env:` for real secrets.** Inline `api_key:` gets logged in error traces and saved to git. And when the key is still missing, don't have it pasted into chat: hand over a no-history ingest one-liner the user runs themselves, then verify the entry (`grep -c '^<KEY_ENV_NAME>' ~/.hermes/.env` — anchor on the name only, a `=...` pattern invites secret scrubbing of the pattern itself) before probing:

```bash
read -rsp '<Provider> API key: ' K; echo "<KEY_ENV_NAME>=$K" >> ~/.hermes/.env; unset K; echo ok
```

**A key found outside `.env` is a finding, not a wiring task.** When a credential turns up somewhere unexpected (credential pool under a mismatched provider ID, a stale `auth.json` entry), report name and location and hand over the ingest one-liner above — do not re-home the discovered key under the "correct" provider ID to clear a 401. The user's key-injection path is theirs to redo the standard way; silently rewiring a discovered key is a repair nobody asked for and it gets undone.

### Pitfall 7 — `delegate_task` is a model tool, and the tool schema has no per-task model

1. **`delegate_task` is a model tool, not a user command.** There is no `/tool delegate_task` and no `/delegate`. The running model calls it when it decides to spawn subagents, so a user asks for delegation through the *goal* ("use a subagent to investigate X in parallel") rather than by naming the tool.
2. **No per-task model override.** The tool schema exposes no `model`/`provider` argument — children inherit the parent's routing, and `delegation.model` / `delegation.provider` in `config.yaml` pin it for *all* children. Never suggest `delegate_task(goal="…", model="…")`; it is not a parameter.

**What works instead:**

1. **Per invocation:** `-p <profile>` — profiles are separate homes (`~/.hermes/profiles/<name>/config.yaml`, no live config inheritance), created with `hermes profile create` (`--clone` copies an existing one), listed with `hermes profile list`, made sticky with `hermes profile use`.
2. **Per session:** `/model <model> --provider <p>` (Pitfall 5).
3. **Per single step:** `hermes -z … --provider <P> -m <M>` — the only route that puts one step on another model while session and children keep theirs.
4. **Advisor plus aggregator:** MoA — `/moa <prompt>` for a one-shot, `hermes moa` to configure the presets (`agent/moa_*.py`).

### Pitfall 8 — Provider config auto-applies once credentials are in the pool

`hermes auth add xai-oauth` (and similar) registers the credential in `~/.hermes/auth.json` and marks the provider as `active_provider`. **You do NOT need to add a `providers:` block to `~/.hermes/config.yaml`** just to enable the provider — Hermes can use `xai-oauth` directly via CLI flags (`hermes --provider xai-oauth --model grok-4.3`) or in the model picker.

Add `providers:` entries only when:
- You want a custom name (`my-xai` instead of `xai-oauth`)
- You have multiple endpoints for the same provider family
- You need to override `base_url` or `api_mode`

If the user says "xai-oauth is configured but Hermes doesn't see it" — verify with `hermes auth status xai-oauth`, not by checking `config.yaml`.

### Pitfall 9 — A documented model or price list is not the current one

Provider doc pages list *curated* models; the provider's own `/models` is the truth, and the two drift in both directions. Quote endpoint output with its fetch time, or re-fetch — never re-cite a docs table as "current". For caps this matters twice over: an undocumented model's limit is unknown, and the doc's headline tier is not necessarily the tier the user is on, so read the plan (or ask) before picking a column.

### Pitfall 10 — Headless OAuth flows are the user's to run

On a headless host (Pi, VPS, container, remote shell) an OAuth provider setup (`hermes auth add xai-oauth --no-browser --manual-paste`, Spotify PKCE, ...) needs a human to paste the callback: started from a tool harness the paste prompt collapses to an **empty string** and the flow fails with `missing authorization code` (or `state mismatch`), because the harness cannot wait out a browser dance happening on another machine. **Hand it over, don't execute it:** give the user the command, the authorize URL and the step list, let them run it in their own terminal, then verify afterwards with `hermes auth status <provider>` — the result is debuggable after the fact, the live flow never is. Even after success the running session does not re-point itself: switch with `/model <model> --provider <provider>` (Pitfall 5) or open a fresh session. Do NOT carry over the old "sessions lock to their starting provider" claim — Pitfall 5 supersedes it.

### Pitfall 11 — A green probe after a credential fix can be the fallback answering

On an auth failure Hermes falls back silently (Knob 3), so a probe that "works" right after a key fix proves only that *some* model answered — often the configured fallback, not the provider you just repaired. Before calling the fix verified, attribute the answer: `state.db`'s `session_model_usage` (`scripts/attribute-provider-burn.py`) names the model that actually served the call, and the provider's server-side 401 log names the one that didn't. Report both sides before claiming the route works.

### Pitfall 12 — A same-named tool is not a trigger for the aux slot

Slot semantics are not trigger semantics: the `session_search` tool is pure FTS5 (its own schema says "no LLM"), catalog search is lexical, and `auxiliary.mcp` serves MCP **sampling** (server-initiated completions) despite the config comment "MCP tool dispatch" — tool dispatch is direct RPC and tool search is BM25, so neither touches a model. Grep the install for `task="<slot>"` call sites before designing a verification around a tool; a pipeline trigger that can fail upstream (e.g. `tts_audio_tags` inside TTS) may never reach the aux call at all. The reliable sequence — config read → bare `call_llm(task=...)` resolver probe → ledger attribution on a real in-session call — is in `references/model-routing-slots.md`; bare out-of-session probes never land in `session_model_usage`.

## References

- `references/model-routing-slots.md` — Which knob moves which model (session / `delegation.*` / `auxiliary.<slot>`), the writer-vs-reviewer rule, the two-step model probe (`-z` answer check, then `-t file`), the full auxiliary slot table, the aux-route verification sequence (trigger map + `call_llm(task=...)` resolver probe + ledger attribution) and the `/review` mechanics.
- `references/live-provider-probes.md` — How to answer "is this key live here", "which models does this plan have", "how much quota is left": key loading without printing values, `/models` + `/usage` response shapes, honest reading of unlabeled percentages, burn attribution from the local ledger (`state.db`, driven by `scripts/attribute-provider-burn.py`), and the credential-visibility chain per consumer.
- `references/model-selection-workflow.md` — Turning a provider plan into config decisions: purposes first, hard filters before ranking, caps as a budget, quality data over the same slugs, which knob each decision lands in, and the probe that closes it.
- `references/opencode-go-plan.md` — OpenCode Go billing facts: the two tiers (Go $10 / Go Plus $40), per-model buckets, Zen-balance overflow, MiniMax M3 on-plan, and the two auth shapes under one base URL.
- `references/opencode-go-api.md` — How to probe the OpenCode Go metadata API: keyed `/models` + `/usage` windows, reading the docs limits-table tabs from raw HTML, auth pitfalls, and detecting new models. The current snapshot lives in the vault (`area/ai/opencode-go-models.md`).
- `references/audio-voice-slots.md` — The `tts:`/`stt:` sections: why German STT fails on the default `stt.language: en`, locale-specific Edge voices, which audio providers each key can serve (and that a ChatGPT subscription is not an OpenAI audio key), Groq as a key-only STT provider, how to verify an audio slot without hearing it, and why desktop dictation (client-direct) leaves no server-side trace.
- `references/request-wire-probes.md` — Capturing what Hermes actually sends to a provider via a throwaway provider entry + echo server: custom-provider reasoning-effort wiring, the off-ladder-level degradation rule, `extra_body` pin semantics, and the per-level impact probe via `reasoning_tokens`.
- `scripts/attribute-provider-burn.py` — aggregates `session_model_usage` over a billing window (per provider/model/task: calls, tokens, plan-priced dollars): the attribution step of "where did my quota go".
- `scripts/voice-config-probe.py` — prints the desktop's resolved client voice config (`mode`/`wire`/`provider`/`model`/`language`, key presence) with secrets masked: the decisive probe for "does dictation work", which server logs cannot answer.
- `scripts/wire-echo-server.py` — localhost capture server that logs the exact request body Hermes sends (stream and non-stream) and answers a minimal completion; pair with a throwaway provider entry to see the wire instead of guessing.
