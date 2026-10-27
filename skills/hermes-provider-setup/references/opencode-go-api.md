# OpenCode Go metadata API — probing and refresh

How to read the OpenCode Go plan state directly from the provider instead of trusting this file or a remembered list. The *current snapshot* of the plan lives in the vault (`akademeia`, `area/ai/opencode-go-models.md`); this file is the procedure, it does not hold data.

## Endpoints

Base URL: `https://opencode.ai/zen/go/v1` (the `model.base_url` of the `opencode-go` provider). Key: `OPENCODE_GO_API_KEY` in `~/.hermes/.env`.

```bash
BASE=https://opencode.ai/zen/go/v1
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'   # required, see below
# 1. model list — the KEYED answer is authoritative (keyless returns the public zen
#    catalogue with extra IDs that fail at request time)
curl -sS "$BASE/models" -H "Authorization: Bearer ***" -H "User-Agent: $UA" | jq -r '.data[].id' | sort
# 2. usage — percentages only, no dollars, no per-model split; three windows
curl -sS "$BASE/usage"  -H "Authorization: Bearer ***" -H "User-Agent: $UA" | jq .
```

`/usage` shape: `usage.rolling.percent / .resetsAt`, `usage.weekly.*`, `usage.monthly.*`.

**Every request to `opencode.ai` needs a browser `User-Agent`.** Cloudflare fronts the host and answers HTTP 403 `error code: 1010` to the default curl/urllib user agent — on the metadata endpoints too, not only on the probes below. A bare `curl` that 403s is not a broken key.

## Auth pitfalls

- The Go key is required for both endpoints; `/models` without a key answers with a different (larger) catalogue and is not a basis for config.
- The usage endpoint can reject a valid key with HTTP 401 (seen 2026-10-20). If that happens, the key may need rotation; the dashboard remains the fallback for quota until the endpoint re-opens.
- The key value never belongs in the vault or in logs.

## Docs page — read the HTML, not a text extraction

The pricing page `https://opencode.ai/docs/go` renders the two plans as **tabs** (Go | Go Plus). A naive text extraction shows only the active tab, so the Go Plus caps go invisible — fetch the raw HTML and parse every `<table>` (one per plan, plus request limits and the model-id map).

- The **limits table is authoritative for per-model caps and prices**; the model list on the docs page lags behind the live `/models` (docs named 30 when the plan served 37).
- Several plan models have no docs row at all → no published cap. Treat that as *unknown*, never as zero or unlimited.
- Two price tiers per model appear as separate rows (off-peak/peak for DeepSeek; ≤/> token split for Qwen3.7 Plus, GPT 6/5.6 Luna, Claude Haiku 5.5, Grok 4.7).

## Detecting changes

Refresh = re-run the keyed `/models` + `/usage`, re-parse the docs tables, then diff against the vault note. Report the delta (added/removed IDs) in both directions and re-date the note — do not re-cite an older snapshot.

Three things the diff itself does not tell you:

- **Join on exact slugs.** The docs tables carry display names ("Claude Haiku 5.5"), `/models` carries ids (`claude-haiku-5-5`); a normalized join (lowercase, strip `.`/`-`) produces false pairs and phantom "unpriced" hits. Map display name → id one row at a time, then close with a count check: served ids = priced ids + served-but-unpriced + documented-but-not-served. If that arithmetic does not close, a join is wrong.
- **Served is not reachable.** An ID in the keyed list proves the key may name it, not that the transport the slot uses can reach it — some ids exist only on another protocol surface (`ModelProtocolUnsupported` on `/chat/completions`), and Anthropic-shaped models answer only on `/messages`. Probe one completion on the surface the slot would use before recommending a new ID.
- **The delta has config consequences.** A renamed or removed ID is not just a note update — grep every profile's config for the old slug before declaring the refresh done (SKILL.md Pitfall 14).

## Session header

Hermes builds from PR #101864 send the `x-opencode-session` header on main and auxiliary OpenCode requests (merged after v0.21.0). Not needed for the metadata endpoints. On chat calls the relay has answered HTTP 400 `MissingSessionID` without it (SKILL.md, "Wire Probes" section), while a headerless non-streaming `/chat/completions` probe has also been seen to pass — treat the header as required on chat, send any value (Hermes uses the conversation key, else an ephemeral `oneshot-<hex>`), and never read a headerless success as a guarantee.

## Measuring own throughput / latency

AA free-tier values (above) are the reference, but they cover a subset (family-level) and come from external infrastructure. To measure **your** token latency on this key, probe the model directly.

Method (used 2026-10-20 for five models):

- Non-streaming completion, ~1,200 input tokens, `max_tokens: 600`, 3 runs per model.
- Latency = end-to-end (request → full body), not TTFT — includes network + queueing.
- Surface: `/chat/completions` (OpenAI-compatible, `Authorization: Bearer`) for most models; Anthropic-shaped models (`claude-haiku-5-5`, MiniMax, Qwen) must go to `/messages` with `x-api-key` + `anthropic-version` — the `/chat/completions` surface returns HTTP 400 `ModelProtocolUnsupported` for them.
- **Cloudflare blocks plain urllib with HTTP 403 `error code: 1010`** — a browser `User-Agent` header (e.g. `Mozilla/5.0 … Chrome/126.0`) is required.
- `max_tokens` may be hit (all 3 runs exactly 600) → the real tok/s is higher; report the truncation.

```python
# probe_ocg.py — usage: python3 probe_ocg.py <model> [<model>…]
import sys, time, urllib.request, urllib.error, json, os
KEY = os.environ.get('OPENCODE_GO_API_KEY','')
BASE = 'https://opencode.ai/zen/go/v1'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
TEXT = ("Erkläre in präzisem Deutsch, wie ein Transistor funktioniert. "
         "Nenne die drei Anschlüsse und den Unterschied zwischen NPN und PNP. "
         "Schreibe etwa 150 Wörter. Sei sachlich.") * 8

def probe(model, n=3):
    if model == 'claude-haiku-5-5':
        url, payload = BASE + '/messages', {"model": model, "messages":[{"role":"user","content":TEXT}], "max_tokens": 600}
        headers = {"x-api-key": KEY, "anthropic-version": "2023-06-01", "Content-Type":"application/json", "User-Agent":UA}
    else:
        url, payload = BASE + '/chat/completions', {"model": model, "messages":[{"role":"user","content":TEXT}], "max_tokens": 600, "stream": False}
        headers = {"Authorization": f"Bearer {KEY}", "Content-Type":"application/json", "User-Agent":UA}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    toks, lat = [], []
    for _ in range(n):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            t1 = time.time()
            d = json.loads(body); u = d.get('usage', {})
            toks.append(u.get('completion_tokens') or u.get('output_tokens') or 0)
            lat.append(t1 - t0)
        except urllib.error.HTTPError as e:
            return ('HTTP', e.code, e.read()[:300].decode(errors='replace'))
        except Exception as e:
            return ('ERR', str(e)[:300])
    return ('OK', toks, lat)

for m in sys.argv[1:]:
    r = probe(m)
    if r[0] == 'OK':
        print(f"{m}: output_tokens={r[1]} latency_s={[round(x,2) for x in r[2]]} tok/s={[round(r[1][i]/r[2][i],1) for i in range(len(r[1]))]}")
    else:
        print(f"{m}: {r}")
```

Report the per-run numbers (not just a mean), a truncation note where `max_tokens` was hit, and the date. These are your measurements — they complement, not replace, the AA family medians.
