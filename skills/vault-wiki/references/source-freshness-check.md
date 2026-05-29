# Source Freshness Check

Re-extract remote sources (git repos, articles) and compare content against
the stored sha256 to detect updates. Works for all source types that have
a retrievable `source_url`.

## How It Works

| Step | What | Tool |
|------|------|------|
| ① | Find raw sources with a `source_url` field | `search_by_frontmatter` |
| ② | Re-extract the current content from the remote URL | `web_extract` |
| ③ | Compute sha256 of the fresh content | `terminal: sha256sum` |
| ④ | Compare against stored sha256 in frontmatter | Manual comparison |
| ⑤ | Report drift → user decides on re-ingest | Report + ask |

Unlike `git ls-remote` (which only tells you if there are new commits), this
compares **actual content** — a commit that only changes the CI config won't
trigger a false positive, but a README update will.

## Prerequisites

Raw sources must have `source_url` and `sha256` in frontmatter:

```yaml
---
source_url: https://github.com/owner/repo   # or https://example.com/article.html
ingested: 2026-05-28
sha256: a3f2c8b1...   # REQUIRED — set at ingest time
---
```

Sources without `source_url` or `sha256` cannot be checked — report them once.

## Workflow

### ① Find checkable sources

```bash
mcp_turbovault_search(query="source_url:")
```

Filter to `wiki/<domain>/raw/` paths. Each result is a candidate.

### ② Determine the re-extract URL

For each candidate, determine the correct URL to re-extract:

| Frontmatter clue | Re-extract URL |
|-----------------|----------------|
| `source_url: https://github.com/owner/repo` | `https://raw.githubusercontent.com/owner/repo/main/README.md` (try `main` first, fall back to `master`) |
| `source_url: https://raw.githubusercontent.com/...` | Use `source_url` directly |
| `source_url: https://arxiv.org/abs/...` | Use `source_url` (web_extract handles arxiv PDFs) |
| `source_url: https://...` (any other) | Use `source_url` directly |

For GitHub repos, the raw README URL may differ. Try these in order:
1. `https://raw.githubusercontent.com/owner/repo/main/README.md`
2. `https://raw.githubusercontent.com/owner/repo/master/README.md`

### ③ Re-extract and compare

1. Extract fresh content from the URL using `web_extract`
2. Save the result to a temp file via `mcp_turbovault_write_note`
3. Hash it via terminal: `sha256sum /tmp/fresh-source-check.md`
4. Compare with stored `sha256` in the raw source's frontmatter

Compare the new sha256 (first 16 chars) against the stored `sha256` in the
raw source's frontmatter:
- **Match** → content is identical. Skip.
- **Mismatch** → content has changed since ingest.

### ④ Report and offer action

For each drifted source, report:

> **Source:** `wiki/<domain>/raw/articles/<file>.md`
> **URL:** `<source_url>`
> **Stored sha256:** `a3f2c8b1...`
> **Current sha256:** `def789a0...`
>
> This source has changed since it was last extracted. Should I re-ingest it
> and update the wiki pages derived from it?

### ⑤ Re-ingest (if user confirms)

1. Update the raw source content (`write_note` with fresh content)
2. Update `sha256` in frontmatter (`update_frontmatter`)
3. Update existing wiki pages with new information
4. Update `<name>-wiki.md` and `log.md`

**Clean update, not full re-ingest** — existing pages are updated in place,
not re-created. This preserves cross-references and avoids duplicates.

## Limitations

| Scenario | Limitation |
|----------|-----------|
| **Paywalled articles** | Re-extract returns a summary instead of full text — comparison is unreliable. Skip these. |
| **Deleted/renamed repos** | `web_extract` fails (404). Report the source as unreachable. |
| **Non-README docs** | Only checks the main page. If the source ingested multiple pages (docs/, wiki/), each needs separate tracking. |
| **Rate limiting** | GitHub raw URLs are rate-limited to ~60 req/hour without auth. Batch checks or use a token. |

**Rule of thumb:** If a source was paywalled or truncated on first ingest,
skip it on freshness check too — the situation hasn't changed.

## Scope Recommendation

Run this check only when the user explicitly asks:
- "Check if any of my tool sources have updates"
- "Freshness check for my wiki sources"
- "Any new content in my git repos?"

Do NOT include it in the standard lint workflow (it's expensive: N network
requests per run, vs. local-only checks).
