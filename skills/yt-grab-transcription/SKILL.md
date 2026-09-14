---
name: yt-grab-transcription
description: Use this skill when you need a YouTube video's transcript for AI-agent consumption — fetching auto-generated subtitles via yt-dlp, cleaning the duplicated rolling-window lines, and keeping a compact provenance record instead of a full metadata dump.
metadata:
  source: https://github.com/olafgeibig/skills
  version: "0.1.0"
---

# YT Grab Transcription

Fetch the spoken content of a YouTube video as compact plain text suitable for
an AI agent to read (typically ~1 k tokens per 6-minute video). This skill
covers fetching, de-duplication, and a minimal provenance record. It does NOT
download video or audio, and it does not correct ASR errors — hand the cleaned
text to the `transcript-fixer` skill when domain vocabulary matters.

## When to Use

- "Summarize this YouTube video" / "Was steht in diesem Video?"
- Video content must land in a note, vault entry, or agent context
- A pasted `yt-dlp --dump-json` file is suspected to be the wrong artifact for transcript work
- Verifying what a video says before citing it

## Prerequisites

- `yt-dlp` installed and recent (`brew install yt-dlp`)
- Network access to youtube.com
- Node.js (for `scripts/clean-srt.js`; optional if SRT with timestamps is kept as-is)

## How to Run

All commands below are invoked through the `terminal` tool from the directory
where the transcript files should land.

1. **Fetch the auto-subtitle as SRT:**

   ```bash
   yt-dlp --skip-download --write-auto-subs --sub-lang de --convert-subs srt -o "transcript" "<VIDEO_URL>"
   ```

   This writes `transcript.<lang>.srt`. The `-o` template applies to the
   subtitle file just like to a download. Use `--sub-lang en` (or a
   comma-separated list) for other languages.

2. **Clean the rolling-window duplication** (see `## Pitfalls`):

   ```bash
   node scripts/clean-srt.js transcript.de.srt transcript.de.txt
   ```

   `transcript.de.txt` is the agent-ready text. Keep the SRT only when
   timestamps are needed for locating/citing passages.

3. **Capture a one-line provenance record** (stdout, not a file):

   ```bash
   yt-dlp --skip-download --print "%(id)s | %(title)s | %(uploader)s | uploaded %(upload_date)s | %(duration_string)s | %(view_count)s views" "<VIDEO_URL>"
   ```

   Store these fields next to the transcript (e.g. in a note frontmatter) so
   the source stays citable. `id` + `upload_date` are the stable identifiers.

## Quick Reference

```bash
# fetch (German auto-captions -> SRT)
yt-dlp --skip-download --write-auto-subs --sub-lang de --convert-subs srt -o "transcript" "URL"

# de-duplicate -> plain text
node scripts/clean-srt.js transcript.de.srt transcript.de.txt

# metadata for provenance (stdout)
yt-dlp --skip-download --print "%(id)s | %(title)s | %(uploader)s | %(upload_date)s | %(duration_string)s" "URL"

# which subtitle languages exist
yt-dlp --skip-download --list-subs "URL"
```

## Procedure

1. Run the fetch command. Expected output ends with
   `[download] 100% of ...` and the file `transcript.<lang>.srt` appears
   (inspect with `read_file`, limit the first ~40 lines).
2. Check the SRT shape: each block has an index line, a `HH:MM:SS,ms --> ...`
   line, then one or two text lines. If the first text line of block N repeats
   the last text line of block N-1, the cleaner applies.
3. Run `node scripts/clean-srt.js` — it prints `blocks=N lines=M`. Sanity:
   `M` is roughly half of `N` for typical auto-captions.
4. `read_file` the first ~20 and last ~10 lines of the `.txt` to confirm the
   text is continuous and not doubled.
5. If the text will be cited for domain content, route it through
   `transcript-fixer` with the relevant glossary before use.

## Pitfalls

- **`--dump-json` is the wrong artifact for transcript work.** It contains no
  spoken text at all: `subtitles` is `{}` because subtitles are not fetched
  without `--write-subs`, and `automatic_captions` is ~90 % of the file —
  merely `timedtext` API URLs whose signatures expire within hours. A
  6-minute video produces ~564 KB of that with zero transcript content.
  Keep `--dump-json` only if the full stream/format metadata is actually
  needed.
- **json3 is bloated for this purpose:** for the same video the json3 file
  was ~76 KB while the plain speech text is ~4.4 KB. Prefer `srt` (or `vtt`);
  convert from them, not the other way around.
- **Rolling-window duplication:** YouTube auto-captions are delivered as a
  rolling window — each segment contains the previous line plus the new one.
  yt-dlp converts this 1:1 to SRT, so every sentence appears 2-3 times in
  consecutive blocks. Keep only the LAST text line of each block
  (`scripts/clean-srt.js` does exactly this; measured reduction 21.2 KB ->
  4.1 KB, ~81 %).
- **`--print` writes to stdout.** Combining `--print` with
  `--skip-download` and no `--write-auto-subs` creates no file at all — only
  metadata lines on the console. `-o` only names output files; it does not
  redirect `--print`.
- **Impersonation warning is harmless:** `WARNING: The extractor specified to
  use impersonation ... no impersonate target is available` can appear while
  the subtitle still downloads fine. Do not "fix" it.
- **ASR output has real errors** (measured: "fortstunde" for
  "fortschreitende", "Sachsenanhalt" for "Sachsen-Anhalt"). Fine for
  summarization, not fine for verbatim quotes — verify against the video or
  run `transcript-fixer`.
- **Auto-captions may not exist.** If the fetch produces no subtitle file,
  check `yt-dlp --list-subs` for manual subtitles; otherwise the content path
  is audio + local whisper, which is out of scope here.

## Verification

```bash
wc -c transcript.de.txt        # ~4-5 KB for a 6-minute video; 10x+ larger signals leftover duplication
head -10 transcript.de.txt     # first lines must not repeat each other
```

The `.txt` line count being roughly half the SRT block count, plus a non-repeating
`head`, proves the cleaner ran on the right file.
