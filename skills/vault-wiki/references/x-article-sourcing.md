# Extracting X Articles as Wiki Sources

**→ Trigger:** Load this reference from the ingest workflow (step ②) when the source is an X.com URL. Do NOT load this for non-X sources.

X Articles (long-form posts) are JS-rendered and cannot be extracted with `web_extract`. Use the xurl CLI instead.

## Prerequisites
- xurl installed and authenticated (`xurl auth status` must show a valid oauth2 token)
- The xurl skill loaded: `skill_view(name='xurl')`

## URL Resolution First

Before assuming a URL is an X article, **resolve short URLs** (t.co, bit.ly, etc.) first to check what kind of content it is:

1. Try `web_extract` with the short URL — it follows redirects and returns the resolved page type
2. If it redirects to an X article URL (`x.com/.../status/...`), proceed with xurl
3. If it redirects to a blog/article (Medium, TDS, blogspot, etc.), use `web_extract` directly — no xurl needed
4. If curl/web_extract time out on the t.co URL, try again with a longer timeout or use an alternative resolver

This prevents the common pattern of assuming `t.co/xyz` is an X post when it actually points to an external article.

## Author Check Before Routing

Never infer the author from a URL substring — near-identical handles (prefix
collisions, typos) are often different people. Fetch the source first, verify
the author in the response (`includes.users[].username`/`name`; README credits
for repos), then route: same author + different content → new ingest; same
author + same content → duplicate path; different or unknown author → new
ingest with a new entity.

## Pointer Resolution: Find the Referenced Artifact

**Signal:** the post points at an artifact ("clone GitHub below", "my repo below", "read the deep dive"), but `data.entities.urls[]` carries only media/mention links — or the only URL is the article-card link (`x.com/i/article/<article_id>`). Don't stop at the main tweet.

1. **Harvest the author's self-reply/thread, don't guess:** `xurl "/2/tweets/search/recent?query=conversation_id:<tweet_id>&tweet.fields=note_tweet,entities,created_at&expansions=author_id&user.fields=username"` — collect the URLs across all hits and filter by domain (e.g. `github.com`). The artifact is almost always in the author's own reply, not the main tweet.
2. **The linked tweet is often a thread child** (its text is just a link): fetch the child tweet with `tweet.fields=conversation_id,public_metrics`, then search `conversation_id:<id>` across the whole thread and sort ascending by `created_at` — the parent carries the thesis, artifact link, and reply caveats. Record both metric sets in the note: **parent metrics are the signal, child metrics are only the link path.**

## Extraction Command

Once you have confirmed the URL is an X article, extract the tweet ID (e.g., from `https://x.com/user/status/2053231239721885918` → `2053231239721885918`), then:

```bash
xurl "/2/tweets/TWEET_ID?tweet.fields=article,author_id,created_at&expansions=author_id&user.fields=name,username"
```

## Response Fields

The JSON response contains:
- `data.article.plain_text` — complete article body as plain text (the main content)
- `data.article.title` — article title
- `data.article.preview_text` — first ~200 characters
- `data.article.entities.urls[]` — all links referenced in the article; depending on the capture an entry may carry only `text` (the URL itself) instead of `expanded_url` — read both fields, or the article looks link-free and the note's repo/doc list stays empty
- `data.article.entities.mentions[]` — @mentioned users
- `data.created_at` — publication timestamp
- `includes.users[0].name` / `username` — author info

## ⚠️ Pitfall: Never Truncate with `head` or `tail`

X Articles routinely exceed 10,000–20,000 characters. **Never** pipe through `head` or `tail` — this silently truncates the article, and the missing second half may contain critical sections (profiles setup, cron patterns, integration workflows).

```bash
# ❌ TRUNCATED — loses everything after first 100 lines
xurl "/2/tweets/...?tweet.fields=article" | head -100

# ✅ FULL CAPTURE — preserves entire article
xurl "/2/tweets/...?tweet.fields=article" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['article']['plain_text'])"
```

**Consequence of truncation:** A truncated 4,000-char article looked complete (first sections: intro, memory, skills). Missing sections (profiles, cron, Claude Code integration, directory layout) were only discovered days later when the user noticed gaps. The downstream wiki pages created from the truncated source were missing half the article's content.

**Rule:** After extraction, spot-check the `plain_text` length. X Articles are typically 8,000–20,000 characters. If you have <5,000, you likely truncated. Re-extract with full capture before saving.

## Thin/Pointer Posts (No `article`)

**Signal:** `tweet.fields=article` returns no `article` and `data.text` is thin (a claim + one link/image, no substance): a setup pointer (`mcp add`, product URL, install one-liner) or a claim/thesis tweet whose substance lives in an attached image or just names a method family — xurl recovers neither.

- **Co-source the substance into the same raw note at creation time** (raw sources are immutable during normal ingest): official docs (homepage, docs page, GitHub README) for setup pointers; secondary practitioner articles (vendor blogs, Medium/TDS, matched via `web_search`) for claim tweets. Only co-source sources that actually substantiate or extend the tweet's claim — and say so in the note.
- **Record in the raw note that the attached image was not recoverable** — image-only tables/diagrams do not survive the API; don't pretend it was read, and tell the user what's missing.
- **Label marketing vs docs numbers** (a tweet's "17k+" vs the docs' "27k+"); cite co-sourced arXiv IDs in the raw note so pages can point at primary literature.

## Saving as Raw Source

Use the plain_text as the body of a `raw/articles/<descriptive-name>.md` file in the
target wiki (`wiki/<target>/raw/articles/...`). Include:

```yaml
---
title: "Article Title"
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: source
tags: [relevant tags]
source: https://x.com/username/status/TWEET_ID
---
```

Note: The path `raw/articles/` is relative to the target domain wiki. When saving
via TurboVault, use the full vault path:
`mcp_turbovault_write_note(path="wiki/<target>/raw/articles/<name>.md", content=...)`

Add author, date, and platform in the header paragraph.

**Attribution caveat:** a GitHub user search for the X handle returning 404 does not mean the repo doesn't exist — the X handle is not the GitHub owner. Take the repo owner from the thread/article links and record the deviation in the note (otherwise the note credits the artifact to the wrong author).

## Companion URL Supersession

If a second URL arrives in quick succession for the same author/topic and is
substantially richer (10× content — HF Space, repo, blog post), it supersedes
the first: ingest only the richer source; log the first as "Prior ingest not
applied" with the reason. Never double-ingest both.

## HF Space Sources — Bridge to the Companion Repo

`huggingface.co/spaces/<user>/<space>` renders as a shell; `web_extract` returns
a truncated summary. Fetch it once for topic/author + the companion repo link,
then ingest the canonical README via
`curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md` (HF
Space URL stays canonical; likes/dates are freshness signals). Docs repo wins
when two repos exist; no companion repo → the truncated extract is all there
is, ask the user first.

If the user wants the source added to an `area/` bookmarks file, load
`references/bookmarks-bridge.md` for the cross-layer bridge.
