# Which-Knob / Slot Routing: Session, Subagents, Side Tasks

Extracted from `SKILL.md` (v0.7.0). Everything here is verified against the installed Hermes source; the body keeps only the decision stubs.

## Which Knob Decides Which Model: Session, Subagent, One-Shot

Three separate knobs, easy to confuse:

| Scope | Config key | Controls |
|---|---|---|
| Session / main thread | `model.default` + `model.provider` | the model you are talking to; also the default for `hermes -z` unless overridden |
| Subagents | `delegation.model` + `delegation.provider` | what **every** `delegate_task` child inherits — no per-child override exists in the tool schema |
| One run | `hermes -z "<prompt>" --provider <P> -m <M> -t <toolsets>` | that invocation only: fresh context, own session, own tool grants |

Read the value before quoting it (`hermes config get delegation.model`) — the model picker and other sessions write these keys, so a value read earlier in the day can already be stale.

**Separating writer from reviewer.** Because all subagents inherit `delegation.model`, an implementer and a reviewer dispatched through `delegate_task` run on the *same* model — correlated blind spots, which defeats the review. Keep `delegation.*` on the cheap model for the writers and run each review as a pinned one-shot:

```bash
hermes -z "$REVIEW_PROMPT" --provider <P> -m <M> -t file,terminal
```

## Slots outside the three layers

Five more top-level config sections carry model choices; an audit of "every place a model is
configured" must name them too:

| Section | Routes | Read back |
|---|---|---|
| `tts`, `stt` | the audio subsystems — `tts.<provider>.*` / `stt.<provider>.*` hold per-provider models and voices, `tts.provider` / `stt.provider` select the one that runs | `hermes config get tts.provider` (depth: `references/audio-voice-slots.md`) |
| `x_search` | the model behind the X/Twitter search tool | `hermes config get x_search` |
| `moa` | Mixture-of-Agents presets (`hermes moa` writes them) — distinct from the auxiliary `moa_reference` / `moa_aggregator` slots above | `hermes config get moa` |
| `smart_model_routing` | the routing rules that steer which model serves a call | `hermes config get smart_model_routing` |

Because `tts`/`stt` are subsystems rather than single fields, "checked `tts:`" is not an audit — walk the
per-provider subkeys. Desktop dictation resolves on top of `stt:` through the client-direct layer
(`references/audio-voice-slots.md`), so judge speech input by the resolver output, not the YAML.

If the user wants review independence *without* paying for a strong implementer, prefer the native `review` slot (see "Auxiliary (side-task) model slots" below) over a hand-rolled one-shot. When the user decides that implementer and reviewer should both run on `delegation.model`, that is a legitimate call — name the correlated-blind-spot trade-off once, then follow their choice.

**Probe before building on a model.** The model list in `provider_models_cache.json` is a catalogue, not a credential check — a model can be listed and still fail on auth, credits or billing. Two probes, in this order:

```bash
# 1. can it answer at all? (fails in seconds when credentials are missing)
hermes -z "Antworte exakt mit dem Wort BEREIT, sonst nichts." --provider <P> -m <M>

# 2. do its tools work? (a model that answers can still have no file access)
hermes -z "Lies <absolute file path> und antworte in einem Satz: <one verifiable question>" --provider <P> -m <M> -t file
```

A failed probe names the missing piece verbatim — no access token, no credentials, invalid refresh token, no credits, billing required. That string is what the user needs to fix it; report it instead of a generic "provider does not work". Availability is per-credential and changes between sessions, so re-probe rather than trusting a note from an earlier session.

## Auxiliary (side-task) model slots

Hermes routes side tasks through their own slots under `auxiliary:` in `config.yaml` — a third layer next to `model.*` (session) and `delegation.*` (subagents). Each slot takes `provider` / `model` / `base_url` / `api_key` / `timeout` / `extra_body` (some add `reasoning_effort` or an `enabled` flag); an empty model means `auto` (parent credentials). Default timeouts run from 8 s (`memory_query_rewrite`) to 600 s (`curator`).

| Slot | Runs |
|---|---|
| `review` | the `/review` reviewer subagent (see below) |
| `curator` | the background skill-maintenance pass |
| `background_review` | the post-turn self-improvement fork (memory / skill saves) |
| `compression` | context-compression summaries |
| `approval` | the tool-approval classifier — a fast/cheap model is recommended |
| `triage_specifier`, `kanban_decomposer` | the kanban specifier and decomposition passes |
| `monitor` | high-volume scorers (e.g. important-mail 0-10) — a small model is fine |
| `mcp` | MCP **sampling** requests only — an MCP server asking the client to run an LLM completion (`tools/mcp_tool_sampling.py`). Tool dispatch is direct RPC and tool search is BM25 — neither touches a model, despite the config comment "MCP tool dispatch" |
| `title_generation`, `skills_hub`, `vision`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `goal_judge`, `moa_reference`, `moa_aggregator` | whatever the name says |

**The `compression` slot has a window requirement the others do not.** It summarises up to the session's compression threshold (default 75 % of the session window), so its context must clear that number. When it does not, Hermes does not fail — it **lowers the session threshold to the compressor's window** and warns, so the session compresses earlier and carries less context; below 64,000 tokens (`MINIMUM_CONTEXT_LENGTH`) it refuses the model outright. Summary *output* is capped at 10,000 tokens, so output headroom never binds. `auxiliary.compression.context_length` overrides a wrong detected window. Consequence: a cheap small-window model is right for the tiny-prompt volume slots and wrong here — for `compression` the window decides, after that price.

**Tiering the slots.** Three questions sort them: how many calls, how much judgment, how much context. High-volume / low-judgment (`approval`, `monitor`, `title_generation`, `tts_audio_tags`, `skills_hub`, `mcp`, `memory_query_rewrite`, `profile_describer`) → the cheapest model with a wide cap; these prompts are tiny, so their window is irrelevant. Judgment (`curator`, `background_review`, `goal_judge`, `triage_specifier`, `kanban_decomposer`) → a mid-tier strong model, few calls per session. `compression` → window first. `review` → the strongest model reachable, ideally on a *different provider* than the session, so the review neither inherits the writer's blind spots nor spends the session's quota.

**Speed-class models (700+ tok/s) rank on latency, not cost.** Throughput pays where a call is synchronous on a human-visible path, fires often and emits little — exactly the high-volume / low-judgment group above. It buys nothing on the judgment group (the budget there is correctness; a downgrade saves milliseconds nobody sees and costs quality where it matters) and little on `compression` (long input = prefill-bound, so decode speed matters less than the window requirement).

### Verifying an aux slot's route

Slot semantics are not trigger semantics: a slot whose name matches a tool or feature does not mean that path exercises the slot. Grep the install for the call sites before designing a verification around a tool:

```bash
rg 'task="<slot>"' <install root> -g '*.py'
```

Then verify in three steps, cheapest first.

**Step 1 — config read:** `hermes config get auxiliary.<slot>` shows what the config claims.

**Step 2 — bare resolver probe:** one `call_llm(task=<slot>)` through the aux client, outside any session. This exercises routing without waiting for the task's real trigger (and a pipeline trigger that can fail upstream — a TTS synthesis failure aborts before `tts_audio_tags` fires — proves nothing):

```bash
cd <install root>
<runtime python> -c "
import sys; sys.path.insert(0, '<install root>')
import hermes_bootstrap  # sets up the dependency path
from agent.auxiliary_client import call_llm
print(call_llm(task='<slot>', messages=[{'role':'user','content':'Antworte mit einem Wort: pong'}], max_tokens=8))"
```

`<runtime python>` is the interpreter the `hermes` launcher shim execs (`head -2 "$(readlink -f "$(which hermes)")"`); a checkout's own `.hermes/bin/` may hold only the shim, not a python — do not assume a venv interpreter exists.

**Step 3 — ledger attribution:** after the first genuine in-session call of that task, read `state.db`'s `session_model_usage` for `task`, `model`, `billing_provider`, `billing_base_url`. Bare out-of-session probes are **not** ledgered — only session-loop calls land there — so step 2 proves the resolver and step 3 proves the production route.

Configure interactively: `hermes model` → "Configure auxiliary models" (same picker in the dashboard's Models tab). **Read a slot back** with `hermes config get auxiliary.<slot>` (e.g. `hermes config get auxiliary.review`); to see several at once, read the YAML:

```bash
grep -n -A4 "^  review:\|^  curator:\|^  background_review:" ~/.hermes/config.yaml
```

**`/review` — the built-in reviewer.** The slash command (CLI, gateway, TUI, desktop) spawns an independent, full-privilege background subagent on the delegation rail; its result re-enters the spawning session as a normal delegation completion. Model routing: `auxiliary.review` when set, else the parent's credentials (native-SDK providers, `api_mode` detection and credential pools behave exactly as under a `delegation.provider` pin). The reviewer gets the last 10 user/assistant messages (≤12k chars each) plus the names of the skills the parent loaded (≤8), and its goal tells it to investigate the referenced artifacts itself — open the files, read the diff, run the tests — instead of judging the excerpt. Source: `agent/review_engine.py`. The agent cannot call `/review` as a tool — it is user-triggered; for an autonomous run, use the one-shot recipe above with the same provider/model as the `review` slot.
