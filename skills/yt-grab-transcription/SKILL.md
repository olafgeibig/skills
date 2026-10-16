---
name: yt-grab-transcription
description: "Use when fetching a YouTube transcript."
metadata:
  source: https://github.com/olafgeibig/skills
  version: "0.2.0"
---

# YT Grab Transcription

Fetch the spoken content of a YouTube video as text an agent can read. Two
paths exist, and the cheap one is the default:

- **Page extraction (`web_extract`)** — one tool call, no install, no
  post-processing. Enough for summarising, extracting lessons and citing.
- **`yt-dlp`** — only when you need the subtitle *file*: raw SRT/VTT, a
  specific language, or a machine-readable artifact to keep.

This skill does NOT download video or audio, and it does not correct ASR
errors — hand the cleaned text to the `transcript-fixer` skill when domain
vocabulary matters.

## When to Use

- "Summarize this YouTube video" / "Was steht in diesem Video?"
- Video content must land in a note, vault entry, or agent context
- A pasted `yt-dlp --dump-json` file is suspected to be the wrong artifact for transcript work
- Verifying what a video says before citing it

## Path A — page extraction (default)

Call `web_extract` on the plain `https://www.youtube.com/watch?v=ID` URL.
One call returns:

- title, channel, view count, publish date;
- the **description, including chapter timestamps** (the cheapest structural
  map of a long talk);
- a **timestamped transcript** with the rolling-window duplication already
  resolved — no SRT, no cleaner, no Node.js.

The full page is cached at `~/.hermes/cache/web/www.youtube.com-*.md`.

Requirements: network access only. Nothing to install.

**Read the pitfalls before trusting the output** — truncation, proper nouns
and ASR errors all bite on this path.

## Path B — `yt-dlp` (when you need the file)

Use it when Path A is unavailable (no transcript on the page, page blocked) or
when the artifact itself matters: the SRT/VTT, a specific language, or a file
to keep for a pipeline.

Prerequisites: `yt-dlp` installed and recent (`brew install yt-dlp`), plus
Node.js for `scripts/clean-srt.js` (optional if you keep the SRT as-is).

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
   On Path A the description block already carries these fields.

### Quick Reference (Path B)

```bash
# fetch (German auto-captions -> SRT)
yt-dlp --skip-download --write-auto-subs --sub-lang de --convert-subs srt -o "transcript" "URL"

# de-duplicate -> plain text
node scripts/clean-srt.js transcript.de.srt transcript.de.txt

# metadata for provenance (stdout)
yt-dlp --skip-download --print "%(id)s | %(title)s | %(uploader)s | uploaded %(upload_date)s | %(duration_string)s" "URL"

# which subtitle languages exist
yt-dlp --skip-download --list-subs "URL"
```

All commands are invoked through the `terminal` tool from the directory where
the transcript files should land.

## Procedure (Path B)

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

### Path A (page extraction)

- **The inline transcript is truncated head+tail, not complete.** Long videos
  return roughly the first 15 k and last 5 k characters inline, with the full
  text saved to the cache file named in the result footer. Read the omitted
  middle from that file with `read_file` before extracting structure or
  quotes. Assuming the inline text is everything is how the middle of a talk
  silently disappears — the chapters, the strongest arguments and the
  caveats usually live exactly there.
- **Proper nouns in auto-captions are unreliable.** Names come out mangled and
  repeatedly wrong ("Mandy"/"Armadin" for "Mandiant"). Take the correct
  spelling from the video description — which Path A also returns — not from
  the transcript body.
- **Chapter timestamps come from the description, not the transcript.** They
  are human-written and far more reliable than anything derived from the
  caption stream; use them as the note's structure.

### Path B (`yt-dlp`)

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
- **Auto-captions may not exist.** If the fetch produces no subtitle file,
  check `yt-dlp --list-subs` for manual subtitles; otherwise the content path
  is audio + local whisper, which is out of scope here.

### Both paths

- **ASR output has real errors** (measured: "fortstunde" for
  "fortschreitende", "Sachsenanhalt" for "Sachsen-Anhalt"). Fine for
  summarization, not fine for verbatim quotes — verify against the video or
  run `transcript-fixer`.

## Verification

Path A:

- the returned block contains a title, a channel and a timestamped transcript;
- `wc -c` the cache file and confirm you have read past the inline truncation
  if the content is longer than ~20 k characters.

Path B:

```bash
wc -c transcript.de.txt        # ~4-5 KB for a 6-minute video; 10x+ larger signals leftover duplication
head -10 transcript.de.txt     # first lines must not repeat each other
```

The `.txt` line count being roughly half the SRT block count, plus a non-repeating
`head`, proves the cleaner ran on the right file.
