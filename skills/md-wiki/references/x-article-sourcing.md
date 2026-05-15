# Extracting X Articles as Wiki Sources

X Articles (long-form posts) are JS-rendered and cannot be extracted with `web_extract`. Use the xurl CLI instead.

## Prerequisites
- xurl installed and authenticated (`xurl auth status` must show a valid oauth2 token)
- The xurl skill loaded: `skill_view(name='xurl')`

## Extraction Command

Extract the tweet ID from the X URL (e.g., `https://x.com/addyosmani/status/2053231239721885918` → `2053231239721885918`), then:

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

## Saving as Raw Source

Use the plain_text as the body of a `raw/articles/<descriptive-name>.md` file. Include:

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

Add author, date, and platform in the header paragraph.
