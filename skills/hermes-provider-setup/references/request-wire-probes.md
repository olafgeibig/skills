# Request Wire Probes — What Hermes Actually Sends to a Provider

Question class: "does Hermes actually send field X?", "why does the API reject / ignore this parameter?", "which reasoning-effort value reaches the endpoint?". Transport code tells you what it *can* send; only a captured request tells you what it *does*. Capture it.

## Procedure: capture the wire body

1. Start the echo server (record the PID for cleanup):
   ```bash
   python3 <skill>/scripts/wire-echo-server.py 8765 &
   echo $! > /tmp/wire-echo.pid
   ```
   It logs the parsed request body (plus auth/content-type headers) to `$TMPDIR/wire-req-body.json` and answers a minimal valid chat completion (stream and non-stream).
2. Register a throwaway provider pointing at it — one `hermes config set` per field:
   ```bash
   hermes config set providers.<tmpprobe>.name "Probe"
   hermes config set providers.<tmpprobe>.base_url "http://127.0.0.1:8765/v1"
   hermes config set providers.<tmpprobe>.api_mode "chat_completions"
   hermes config set providers.<tmpprobe>.api_key "probe"
   hermes config set 'providers.<tmpprobe>.models' '{"<model-id-under-test>": {}}'
   ```
3. Drive it exactly like the real provider: `timeout 120 hermes -z "sag ok" --provider <tmpprobe> -m <model-id>` — the body is independent of base_url, so the captured shape is the real one.
4. Read the log: top-level keys, and each field you care about (`reasoning_effort`, `reasoning`, `thinking`, `extra_body`, `max_tokens`, `temperature`, `stream`). Note: OpenAI-SDK `extra_body` keys are **flattened into the top level** of the JSON — a captured body never contains a literal `extra_body` field.
5. Cleanup: `hermes config unset providers.<tmpprobe>`, then kill by the recorded PID (`kill $(cat /tmp/wire-echo.pid)`).

**Never `pkill -f <scriptname>` from a command line that contains that same string** — the pattern matches the cleanup shell itself and the command dies with SIGTERM before cleanup finishes. Kill by recorded PID, or use a self-excluding pattern (`'[w]ire-echo'`).

## Verified facts: reasoning effort on a `providers:` (custom) entry

- The custom-provider path sends **top-level `reasoning_effort`** (alongside `model`, `messages`, `tools`, `stream`, `stream_options`) — not the nested `reasoning: {enabled, effort}` shape that some built-in profiles use. This is what OpenAI-compatible reasoning endpoints expect.
- The value tracks `agent.reasoning_effort` (what `/reasoning` sets): `high` on the knob → `"high"` on the wire.
- Hermes' internal ladder is `none/minimal/low/medium/high/xhigh/max/ultra` — the same eight values `/reasoning` and `hermes --reasoning` accept, so a provider-specific level outside it cannot be set interactively at all. A bare string in `agent.reasoning_effort` that is not on the ladder is silently sent as the default `medium` — the write appears to succeed, the wire says otherwise. Never promise an off-ladder level through the global knob; verify on the wire.
- **Off-ladder level, preferred route — per-model override.** Bare strings are strict, but the **dict form passes the level through verbatim**: `hermes config set 'agent.reasoning_overrides' '{"<model-id>": {"enabled": true, "effort": "<level>"}}'` (verified on the wire: `instant` arrives as `"instant"`, other models keep `medium`). Precedence: session `/reasoning` > `agent.reasoning_overrides.<model>` > `agent.reasoning_effort` — so the knob stays usable per session — and per-model keys match spelling-tolerant (exact → dots↔dashes → provider prefix stripped → prefixed-key reverse lookup).
- **Off-ladder level, last resort — provider pin:** `hermes config set 'providers.<key>.extra_body' '{"reasoning_effort": "<level>"}'` lands as a top-level body field and **overrides** the agent-level value (verified: pin `instant` wins even with `agent.reasoning_effort: high`). It makes `/reasoning` inert for that provider — state that trade-off before pinning, and prefer the per-model override above. One recommendation, not a menu.

## Reasoning on auxiliary (side-task) slots

Reasoning on an aux call is configured **per slot** (`auxiliary.<slot>`). Don't assume an agent-level knob or a per-model override reaches an aux call — set the slot's own field and verify the body with the echo probe.

- `auxiliary.<slot>.reasoning_effort` is validated against the Hermes ladder (an off-ladder value like `instant` is logged as invalid and ignored) and, when accepted, folds into **nested** `extra_body.reasoning: {enabled, effort}` — the generic OpenAI-compat shape. A strict custom gateway that wants top-level `reasoning_effort` ignores or rejects it.
- **Top-level wire / off-ladder level: the slot's `extra_body`** — `hermes config set 'auxiliary.<slot>.extra_body' '{"reasoning_effort": "<level>"}'`. Caller reasoning fields merge last, so this lands top-level and wins over profile defaults and the generic nested fallback (verified on a live aux call: body = `messages`, `model`, `reasoning_effort`, `response_format`, value `"instant"`).
- Set exactly **one** of the two: a slot carrying both `reasoning_effort` and `extra_body.reasoning_effort` ships both wire shapes in one body.
- Worth pinning to the no-thinking tier: the high-volume, tiny-prompt slots (`approval`, `title_generation`, `tts_audio_tags`, `skills_hub`, `memory_query_rewrite`, `session_search`) — tiering per slot in `references/model-routing-slots.md`.

To force an aux body through the echo probe without touching the main route: repoint one slot (e.g. `auxiliary.title_generation.provider`/`.model`) at the throwaway probe entry, set its `extra_body`, run a plain `hermes -z` turn (it generates a title), read the log, then restore the slot fields.

## Acceptance/impact probe: does the endpoint honor a level?

One raw `curl` chat completion per candidate level against the real `base_url`, fixed short prompt, then read three things: HTTP status, wall time, and `usage.completion_tokens_details.reasoning_tokens`.

- Non-2xx → the value is rejected; the error message is the authoritative list of accepted values (doc pages lag).
- Endpoints often accept values beyond their documented ladder without error — acceptance is not support.
- Reasoning-token counts on a trivial prompt are noise and not monotonic in the level. Infer only behavior switches (e.g. 0 reasoning tokens = thinking actually off, and it is typically the fastest call), never a quality ordering. If ordering matters, repeat each level several times on a prompt that forces multi-step work and compare medians.
- Worked example (diffusion LLM with a no-thinking tier): a provider whose ladder is `instant/low/medium/high` shows `instant` at 0 reasoning tokens on every run and the lowest median wall time, while `low`/`medium`/`high` overlap within noise on ordinary prompts — so the speed win is the tier switch, not the in-ladder level choice. Prefer the no-thinking default for latency-sensitive use and lift the level per session (`/reasoning high`) when a task needs multi-step work.

## Config-write success is not effect

`hermes config set` can print a "not a recognized config key" warning on a valid key and still write the value (observed with `agent.reasoning_effort`). Verify by readback plus wire probe, and **restore any global knob you changed for a test** (`agent.reasoning_effort` and friends are global — they hit every provider) before reporting.

## Acceptance of a custom effort level on the wire vs. API

Two separate gates, check both: (1) does Hermes put the value on the wire (echo probe), (2) does the endpoint act on it (impact probe). A pin that passes (1) can still be ignored by (2).
