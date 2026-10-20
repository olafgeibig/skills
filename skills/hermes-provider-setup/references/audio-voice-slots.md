# TTS / STT: the audio slots (verified 2026-10-03)

The two model-bearing config sections outside `auxiliary`/session are `tts:` and `stt:`. Both are whole
subsystems, not one model field: `tts.<provider>.*` and `stt.<provider>.*` hold per-provider models and
voices, and `tts.provider` / `stt.provider` select which one runs.

## Why German voice input fails out of the box

`stt.language` **defaults to `"en"`** (deliberately — Whisper auto-detect misreads short or accented
clips) and is NOT written into a user's config. Consequence: a German recording is transcribed as forced
English, no matter how good the model is — faster-whisper `base` on a 10 s clip returned
"Hello Olaf, this is a test of the conversation about Hermes... it works well" for a German sentence.
Set `hermes config set stt.language de` first, then judge the model. With `de` the same local `base` model
returned the sentence verbatim. Per-provider overrides win over the global key
(`stt.<provider>.language` > `stt.language`).

## Built-in providers and what they need

TTS (`tts.provider`): `edge` (free, needs the `edge_tts` package) | `openai` | `elevenlabs` | `minimax` |
`xai` | `gemini` | `mistral` | `deepinfra` | `neutts` / `kittentts` / `piper` (local).
STT (`stt.provider`): `local` (faster-whisper) | `local_command` | `groq` | `openai` | `mistral` | `xai` |
`elevenlabs` | `deepinfra`.

Key facts that decide availability:

- **Edge voices are locale-specific.** The shipped default `en-US-AriaNeural` speaks German text with an
  English voice. Add the locale to the config: `tts.edge.voice: de-DE-FlorianMultilingualNeural` (or
  `de-DE-SeraphinaMultilingualNeural`, `de-DE-KatjaNeural`, `de-DE-ConradNeural`). The `*MultilingualNeural`
  voices handle mixed DE/EN text, which matters when the answer contains English technical terms.
  List them with `edge_tts.list_voices()` filtered on the locale prefix.
- **Groq is a built-in STT provider but never appears as a provider in the credential pool** — it runs off
  `GROQ_API_KEY` alone (default model `whisper-large-v3-turbo`). Measured on a 10 s German clip: Groq
  **1.4 s, verbatim** vs local `base` **10.5 s, verbatim** — same accuracy once `stt.language` is right, so
  the choice is speed vs. sending the audio to a cloud endpoint, not accuracy.
- **xAI TTS works over the subscription OAuth.** `tools/tts_tool.py` comments that the OAuth bearer "403s on
  metered /v1/tts", but a live probe through `xai-oauth` synthesized successfully (log line
  `Generating speech with xAI TTS...`, saved as `provider: xai`); the audio differed byte-wise from the edge
  output for the same text, so it was not a silent edge fallback. `x_search` also runs on `xai-oauth`
  (`grok-4.20-reasoning`, live probe OK). Treat the comment as a hypothesis, the log as the evidence.
- **A ChatGPT subscription is not an OpenAI audio key.** `openai-codex` (device-code OAuth) covers chat via
  the Codex endpoint; TTS/STT need `OPENAI_API_KEY` or `VOICE_TOOLS_OPENAI_KEY`, and without one the call
  fails with `TTS configuration error (openai): ... neither tts.openai.api_key in config nor
  VOICE_TOOLS_OPENAI_KEY/OPENAI_API_KEY is set`. Check `.env` for the key BEFORE promising OpenAI audio.
- **MiniMax TTS runs on the same `MINIMAX_API_KEY` as chat** (defaults `speech-02-hd`, voice
  `English_expressive_narrator`, endpoint `https://api.minimax.io/v1/t2a_v2`); it read a German sentence
  correctly. An exhausted provider key kills its audio too (a 402 `gemini` key = no Gemini TTS).

## How to verify an audio slot without hearing it

1. `text_to_speech(provider=..., text=<short sentence in the user's language>)` — success alone is not proof:
   compare the produced bytes against the same text through the configured provider (`cmp` two files; a
   byte-identical file for a different provider name means a silent fallback to the configured one).
2. Round-trip: transcribe the generated clip and compare with the input text. A verbatim transcript proves
   intelligible speech; a wrong-language transcript usually means `stt.language`, not a broken provider.
3. Read the log line for the engine that actually ran (`grep -i tts ~/.hermes/logs/agent.log`) — the tool
   result names the requested provider, the log names the one that synthesized.

## Desktop dictation is client-direct — logs cannot answer "did it work"

The desktop's speech input does not pass through the gateway: the renderer fetches
`GET /api/audio/voice-config` (`hermes_cli/web_routers/audio.py` →
`tools/voice_client_config.py:resolve_client_voice_config()`) and uploads the recording straight to the
provider (`apps/desktop/src/lib/voice-client-direct.ts`). Know this before debugging voice input:

- **Only three client wires exist** — `elevenlabs-stt`, `openai-multipart` (openai and same-shape riders
  such as groq), `xai-stt`. Anything else resolves to `{mode: "relay", reason: …}` and the gateway
  transcribes. TTS mirrors this (`elevenlabs-tts`, `openai-speech`; `edge` always relays).
- **A working dictation leaves no backend trace.** The audio never touches the gateway host; the only
  server-side sign of a dictated message is the submitted prompt (`tui prompt accepted … kind=user
  chars=N` in `~/.hermes/logs/gui.log`), identical to typed text. An empty transcription log is
  therefore consistent with both "worked" and "failed" — never conclude either from logs.
- **Probe the resolution instead.** `scripts/voice-config-probe.py` (run with the hermes-agent venv
  python) prints `mode` / `wire` / `provider` / `model` / `language` and whether a key is set. Healthy
  German groq dictation reads `mode: direct`, `wire: openai-multipart`, `model: whisper-large-v3-turbo`,
  `language: de`. The `language` field is the effective `stt.language` — the forced-English failure
  above hits dictation exactly as it hits relay STT.
- **`mode: relay` is not automatically broken.** The `reason` string tells the cases apart: a missing
  client wire (`provider 'edge' has no client wire`) is normal for that provider, while a config
  resolution failure also reports relay with the error as `reason`.
- **The client caches the resolution for 60 s**, so a config change is live within a minute without an
  app restart; the upload cap mirrors the gateway `stt` timeout (60 s default).
- **The upload leaves via the client machine's network**, not the gateway host's: a blocked route to the
  provider shows up in the client UI and nowhere on the server.
