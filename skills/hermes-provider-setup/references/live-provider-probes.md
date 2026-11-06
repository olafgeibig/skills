# Live provider probes: inventory, quota, credential visibility

Depth for the SKILL.md sections *Live Provider Inventory and Quota* and *Provider Keys*. Use it when a question turns on **current** provider state (which models, which price, how much quota is left) and no citable doc page can answer it.

## 1. Probe order

1. `config.yaml` — `model.provider`, `model.base_url`, and any `providers.<name>` override. Take the base URL from there; do not retype a docs host.
2. `~/.hermes/.env` — the credential name. Convention: `<PROVIDER_UPPER_SNAKE>_API_KEY` (some providers add `<...>_BASE_URL`). Read the *names* first: `grep -oE '^[A-Za-z_][A-Za-z0-9_]*' ~/.hermes/.env | sort -u`.
3. Probe from the terminal tool with curl, loading the key without printing it:

```bash
export PROVIDER_KEY="$(python3 - <<'PY'
import re, pathlib
for line in pathlib.Path.home().joinpath('.hermes/.env').read_text(errors='replace').splitlines():
    m = re.match(r'\s*(?:export\s+)?THE_KEY_NAME\s*=\s*(.*)$', line)
    if m:
        v = m.group(1).strip()
        if len(v) > 1 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        print(v); break
PY
)"
echo "key len: ${#PROVIDER_KEY}"     # length only — the value stays out of the transcript
```

`set -a; . ~/.hermes/.env; set +a` also works but mis-parses values holding shell metacharacters; the parser above mirrors what Hermes' own loader accepts.

## 2. Endpoint shapes

| Probe | Answer |
|---|---|
| `GET $BASE/models` | live inventory: `{"object":"list","data":[{"id":"…","object":"model","created":…,"owned_by":"…"}]}` — no context window, no price, no cap |
| `GET $BASE/models` **with** vs **without** the key | often two different lists. The keyless answer is the public catalogue, the keyed one the provider's plan-scoped list; the keyless list can contain IDs the plan does not serve, which then fail at request time. Decide from the keyed answer, and state which one you read. |
| `GET $BASE/usage` | windowed quota, where the provider offers it: `{"usage":{"rolling":{"status":"ok","percent":N,"resetsAt":"…Z"},"weekly":{…},"monthly":{…}}}` |
| 404 with an HTML body | not an endpoint. OpenCode-style providers answer unknown paths with the docs page — check the HTTP status before trying to parse JSON. |
| `POST $BASE/chat/completions` without a session header | `400 {"type":"error","error":{"type":"MissingSessionID"…}}` — OpenCode Go wants `x-opencode-session` in addition to the key; Hermes sends it since the build with PR #101864, a raw curl/urllib probe must set it itself. Two auth shapes coexist under one base URL: `/chat/completions` (OpenAI-compatible, `Authorization: Bearer`) and `/messages` (Anthropic shape, `x-api-key` + `anthropic-version`; a Bearer there returns 401), so read the provider's endpoint table before assuming a shape. |
| docs page with plan tabs (e.g. Go / Go Plus) | a text extractor renders only the active tab — the second plan's limit table stays invisible. Fetch the raw HTML and read **every** `<table>`; that is how the $180/$240 caps behind the $40 plan surfaced after an announcement feed had claimed a single price point. Never conclude "this tier does not exist" from a rendered page, a search snippet, or an older announcement. |
| image input | billed as plain input tokens. Prove vision by POSTing a self-generated PNG with known content (PIL is commonly installed) — a catalogue's `image` modality flag is a claim, not evidence; when cheap and expensive candidates both pass a basic OCR test, price and cap decide, not the flag. |

Print the status code and byte count first, then the parsed fields; that is what distinguishes "endpoint missing" from "auth rejected" from "empty plan".

## 3. Reading quota numbers honestly

- Two layers exist side by side: **window caps** (rolling ≈5 h admits 20 % of *that model's* monthly amount, weekly 50 %, monthly 100 % — a $60 model therefore has $12 / $30 / $60) and a **per-model monthly dollar cap**. Both apply, and they are per model, not per account: two models on one provider are two independent buckets, which is what makes splitting roles across models pay.
- `/usage` answers with one percentage per window. That number aggregates — it cannot tell you *which* model's cap is being approached. Take the per-model caps from the provider's limits table and use `/usage` for the overall burn only.
- `percent` is not labeled by the endpoint. Report it as "share of that window's allowance as reported, with `resetsAt`" instead of converting it into money or tokens.
- Only rows the docs explicitly mark as free/unlimited are unlimited; a model absent from the limits table has an unknown cap.

## 4. Credential-visibility chain (why one consumer sees a key and another does not)

- Per turn Hermes installs a secret scope from `~/.hermes/.env` plus hydrated sources: `tui_gateway/prompt_turn.py` → `launch_secret_scope` → `build_profile_secret_scope`. `load_env_file` memoizes on the file's stat identity (mtime/size/inode), so an edited `.env` is picked up without a restart.
- `os.environ` is populated once at process start by `load_hermes_dotenv()` (`hermes_cli/env_loader.py`, called from `tui_gateway/server.py`, `gateway/run.py`, `cli.py`). `/reload` and the `reload.env` RPC re-run it in place.
- Terminal children are assembled by `tools/environments/local.py` (`_scrubbed_env` → `_filter_secret_env`): Hermes-managed credentials are stripped unless registered, and declared passthrough names the secret scope holds but the process env lacks are added back by `scoped_passthrough_additions`. That is why `terminal.env_passthrough` works for a third-party key and why provider credentials are refused there on purpose.
- Check a long-running process's view with `tr '\0' '\n' < /proc/<pid>/environ | grep -oE '^[A-Z_]*'`; check the terminal shell's view with `env | grep -oE '^[A-Za-z_]*NAME[A-Za-z_]*'` (names only).
- A key **name** written into a note can come back masked from a read tool while the file on disk is intact — the masking sits in the tool's output layer, not in the file. Confirm with a count (`text.count('KEY_NAME')`) before concluding a write damaged the file, and never rewrite a file to "fix" a masked display.

## 5. Ready-made probe, and where the inventory lives

- `provider-models-probe` (installed at `~/bin/provider-models-probe`, on `PATH`) prints live model lists for deepseek, groq, gemini, zai, minimax, huggingface and opencode-go plus the OpenCode usage percentages in one call; pass names to narrow it (`provider-models-probe groq zai`). Keys come from `~/.hermes/.env`, values are never printed.
- **User-Agent pitfall:** `api.groq.com` and `opencode.ai` sit behind Cloudflare and answer a default urllib/curl agent with `error code: 1010` — an HTML body that reads like an auth rejection. Send a browser User-Agent (curl: `-A "Mozilla/5.0"`) before diagnosing the key.
- Hosts that carry no `/models`-style list but still need a probe: Cloudflare Workers AI `GET /accounts/<account-id>/ai/models/search` (billed in **neurons**, 10,000/day free, not in tokens) and the Hugging Face router `GET https://router.huggingface.co/v1/models` (only router routes carry published prices; the hub's tens of thousands of repo IDs do not).
- **Where the inventory lives (akademeia vault):** `area/ai/My AI Model Provider.md` — which provider holds which credential, the model/pricing URL per provider, dated probe results, and which `.env` keys are *not* model providers (TAVILY, FIRECRAWL, ARTIFICIAL_ANALYSIS, GITHUB_TOKEN, BROWSERBASE, OPENVIKING, TELEGRAM). Read that note before proposing a provider route; OpenCode Go detail stays in `area/agents/opencode-go-models.md`.

## 6. Burn attribution from the local ledger (`state.db`)

`/usage` says how much of the allowance is gone; the local ledger says **which model spent it**. Table `session_model_usage` in `~/.hermes/state.db` (open read-only, `sqlite3.connect(f'file:{db}?mode=ro', uri=True)` — the file is hundreds of MB and shared with live sessions):

| Column | Meaning |
|---|---|
| `session_id`, `model`, `billing_provider`, `billing_base_url`, `billing_mode`, `task` | the primary key; `task` separates aux slots (`compression`, `vision`, `title_generation`, …) from the session itself (empty string) |
| `api_call_count`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens` | the burn |
| `estimated_cost_usd`, `actual_cost_usd`, `cost_status`, `cost_source` | Hermes' own estimate; **0 for plan providers** (no catalogue price) — never report these as spend |
| `first_seen`, `last_seen` | unix epochs; bound the window with `last_seen >= <cycle start> AND first_seen <= <window end>` |

Recipe: take the cycle start from `/usage` `resetsAt` minus the window length, `SUM(...)` grouped by `billing_provider, model, task`, then price the tokens against the plan's own rows (in / out / cached read per 1M) and state the peak/off-peak basis. `scripts/attribute-provider-burn.py --since <ISO> [--provider P] [--prices prices.json]` does exactly this read-only.

**Attribute on dollars, not token volume.** Long agent sessions re-send most of the context on every call, so `cache_read_tokens` can dwarf `input_tokens` (506 M against 37 M in one 8-day window) while contributing a few percent of the cost at a cache price two orders of magnitude below input. Judging by raw tokens names the wrong hot bucket — and a bucket that is hot in dollars but idle in requests is the one that will block.

**Project, don't declare.** "N % at D days into the cycle" plus a linear projection of the breach day is the honest form; per-window percentages aggregate across models and cannot attribute (§ 3), so the projection and the per-model attribution are two separate claims.

## 7. Comparing Copilot clients: credential, headers, host, then proxy

Use this sequence when Hermes can invoke a model but a proxy or another client cannot. Inspect the active installed direct-API plugin's exchange and header helpers; do not substitute the ACP/CLI implementation.

1. **Resolve both credential chains before probing.** Record each client's source label, credential stage (source GitHub credential versus exchanged API token), resolved API base and expiry. An `env:<NAME>` pool row is metadata, not necessarily an `access_token`; an empty `os.environ` in a terminal child does not prove that the profile credential is absent. Resolve the active profile's source through its loader rather than switching accounts or assuming the default profile.
2. **Compare only allowlisted account metadata.** For an exchange response or a client's API-token cache, inspect fields such as `sku`, `individual`, `chat_enabled`, `expires_at` and the API endpoint. A Business-seat credential and a free-limited individual credential are not equivalent merely because both list the model. Do not print raw tokens, token claim maps, complete auth JSON, complete YAML stanzas or arbitrary response bodies; unrelated config entries can contain secrets too. Keep credentials inside the probe process, out of shell arguments and saved output.
3. **Build one minimal request on the working transport.** Preserve the literal model ID and body across trials, use synthetic input, a bounded output limit and a timeout. Reuse the installed helpers to exchange the source credential and obtain the working client headers. Save only a compact result table: credential label, header variant, host, HTTP status, allowlisted error code and whether generated output was present.
4. **Change one factor at a time.** Establish the working credential + working headers baseline; try the other client's exact headers with that credential; then try the other client's credential with the working headers. Test alternate hosts separately only if still relevant. This isolates credential/account differences from header and endpoint differences without repeatedly re-running every successful trial.
5. **Interpret failures at the right layer.** A missing `Editor-Version` rejection establishes a required IDE-auth header, not model entitlement. If both clients' header sets work with one token while the other token returns `model_not_supported` under the same request, report credential-dependent model access; do not claim the SKU itself is the proven enforcement mechanism. An authenticated enabled catalogue entry cannot overrule the failed inference.
6. **Close the actual client path.** A direct API probe is only upstream evidence. Obtain explicit authorization before reusing a credential in another client; prefer the client's supported secure credential mechanism over pasting tokens into config or replacing short-lived token caches. Then invoke the requested model through the proxy's intended endpoint, validate the response's generated output and model attribution, and test refresh behavior before describing persistent authentication as solved. If no proxy change was made, state that only the upstream path was verified.

Report the decisive comparison and the remaining verification gap, not every exploratory trial. Do not present an unwanted old-model fallback as a solution to a request for a modern model.

## 8. LiteLLM Copilot reauthorization preflight

Use this after § 7 isolates an account/credential difference. This is a safe preparation and verification sequence, not evidence that a replacement login has succeeded.

1. **Inspect the installed authenticator and launcher first.** Resolve the interpreter used by the actual `litellm` executable rather than assuming the shell's Python has the same package. Read the launcher's environment-loading behavior and the authenticator's token-directory override before modifying caches. In versions exposing `GITHUB_COPILOT_TOKEN_DIR`, confirm both the standalone authenticator and proxy use the same explicitly selected directory.
2. **Authenticate outside the proxy when required by the installed version.** If the authenticator explicitly rejects device login inside an event loop or worker thread, a proxy request cannot complete that login. Its diagnostic may prescribe the standalone entry point `from litellm.llms.github_copilot.authenticator import Authenticator; Authenticator().get_access_token()`. Inspect the current implementation before running it, and do not print the returned access token. This entry point starts authorization; it is not proof of completed authorization.
3. **Stage replacement auth separately.** Preserve production caches while the user authorizes the intended account into the candidate directory. Coordinate the short-lived interaction using SKILL.md Pitfall 10. Afterward verify that credentials actually exist and check account/SKU using allowlisted metadata; never infer completion from a process merely starting or from an authorization URL appearing.
4. **Mirror the service environment in an isolated proxy test.** Load the existing master key using the launcher's supported method without displaying it, bind to loopback on a verified unused test port, and select the candidate auth directory explicitly. Do not disable authentication to bypass a missing-key startup refusal. Check liveness, then make an authenticated inference request for the requested model and inspect generated output and attribution. A server may pass liveness while the model has no healthy deployments.
5. **Promote only a verified candidate.** Switch production to the replacement credentials through the supported configuration mechanism, reload only as needed, and repeat inference through the production endpoint. Stop only the temporary process you started. If authorization expires, report no replacement credential and leave production unchanged; if an earlier action already removed active credentials, explicitly disclose that state and offer restoration instead of describing liveness as working service.
