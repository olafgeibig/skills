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
- `data.article.entities.urls[]` — all links referenced in the article
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
