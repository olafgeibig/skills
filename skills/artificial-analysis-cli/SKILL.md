---
name: artificial-analysis-cli
description: "Use when comparing AI models via the model-analysis CLI."
metadata:
  version: "0.1.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - ai-models
      - benchmarks
      - comparison
      - cli
    related_skills:
      - hermes-provider-setup
---

# Artificial Analysis CLI

Read live AI-model data from the Artificial Analysis API through the `model-analysis`
CLI — intelligence/coding/agentic indices, price per 1M tokens, throughput — and turn it
into a comparison the user can act on.

Scope: **data retrieval and comparison only.** This skill never changes Hermes model or
provider configuration; that is `hermes-provider-setup`. It also does not write to the vault.

## When to Use

- "compare model X and Y" / "welches Modell ist besser für <task>"
- benchmark or index values for a named model
- price/throughput check before switching a Hermes provider or model
- "what was released recently" / leaderboard snapshots

## Invocation

The CLI is an npm global (`@skastr0/model-analysis-cli`). `~/.npm-global/bin` is **not** on
the agent's PATH, so call it through the symlink in `~/.local/bin` (created for exactly this
purpose). A bare `model-analysis` in the terminal tool fails with exit 127.

```bash
model-analysis --version             # 0.2.0
model-analysis auth status --check   # live request: tier, HTTP status, rate limit
```

## Authentication and Quota

- The key is read from the shell env `ARTIFICIAL_ANALYSIS_API_KEY` (set in the user's
  bashrc; the terminal tool sources it via `terminal.auto_source_bashrc: true`). It is
  deliberately absent from the dashboard/gateway process env and from
  `terminal.env_passthrough` — do not "fix" that by editing `.env` handling.
- Read the quota from any response: `meta.http.rate_limit` →
  `limit` / `remaining` / `reset` (epoch seconds). Free tier: 100 requests per window.
- Free tier reports `data_shape: "free"` on `/language/models/free`.
- Quota discipline: one `models list` answers most questions — cache it to a file and analyse
  with `jq`. `providers …` and `models performance` are live and uncached; `--refresh`
  re-fetches and spends quota.

## Commands

| Command | Purpose |
|---|---|
| `models list` | full LLM catalog: id, slug, name, creator, release_date, evaluations, pricing, performance |
| `models get <input>` | one model by id or slug |
| `models compare '{"model_slugs":[…] }'` | side-by-side comparison; takes positional JSON |
| `models performance <input>` | performance over time (live, uncached) |
| `models cache status` / `models cache clear` | local catalog cache |
| `media list` | media models for a given media type |
| `providers list` / `get` / `performance` / `measurements` | API providers behind the models |
| `auth status [--check]` | auth configuration; `--check` performs the live request |
| `critpt evaluate <input>` | code grading (approved accounts only, no automatic retry) |

Global flags: `--refresh`, `--cache-ttl-seconds <n>`, `--stale-if-error`,
`--concurrency <n>` (`models compare`), `--log-level <level>`, `--completions <shell>`,
`--wizard`.
Env: `MODEL_ANALYSIS_CACHE_DIR`, `MODEL_ANALYSIS_CACHE_TTL_SECONDS`,
`ARTIFICIAL_ANALYSIS_BASE_URL`.

Output is JSON-first — pipe everything through `jq`, never read it by eye.

```bash
# one request, then analyse locally off the cached file
model-analysis models list > /tmp/ma-models.json
jq '.data | length' /tmp/ma-models.json

# comparison table for a fixed candidate set
jq -r '.data[]
  | select(.slug as $s | ["minimax-m3","deepseek-v4-pro"] | index($s))
  | [.slug,
     (.evaluations.artificial_analysis_intelligence_index // "-"),
     (.evaluations.artificial_analysis_coding_index // "-"),
     (.pricing.price_1m_input_tokens // "-"),
     (.pricing.price_1m_output_tokens // "-"),
     (.performance.median_output_tokens_per_second // "-")]
  | @tsv' /tmp/ma-models.json | column -t -s $'\t'
```

## Answering a Comparison

1. Run `auth status --check` when auth or quota is in question.
2. Fetch `models list` once into a file, then filter with `jq`.
3. Report each index value with its field name, and report `null` fields as
   "not included in the free tier" — never as `0`, never estimated.
4. Put price per 1M input/output tokens and `performance` (median tok/s, TTFT) next to the
   quality index; a quality-only verdict is incomplete.
5. Coverage differs per model (see Pitfalls): a missing index is a data gap, not a bad score.

## Pitfalls

- **Not on PATH**: a bare `model-analysis` call exits 127. Use `~/.local/bin/model-analysis`.
- **Partial free-tier coverage**: in one full catalog snapshot (689 models) the
  intelligence index was present on 680, coding on 258, economics 213, engineering 205,
  agentic 164, healthcare 80. `null` means "not in this tier".
- **No raw benchmark results**: only the aggregated `artificial_analysis_*_index` fields;
  MMLU/HumanEval-style raw scores are not part of the free shape.
- **Small quota**: 100 requests per window. One `models list` plus `jq` beats many
  `models get` calls. A spent quota surfaces as a failing tool — check `remaining` first.
- **`compare` wants JSON on the command line** (`'{"model_slugs":[…] }'`), not a list of plain
  arguments; unescaped quotes break it.
- **Do not invent scores**: if a slug is missing from the catalog, say so instead of mapping a
  similarly named model.

## Verification

```bash
model-analysis --version
model-analysis auth status --check | jq -r '.data.status, .meta.http.rate_limit.remaining'
# expect: 200 and a positive remaining count
```
