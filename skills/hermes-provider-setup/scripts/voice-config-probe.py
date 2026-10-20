#!/usr/bin/env python3
"""Print the resolved CLIENT voice config — what desktop dictation actually uses.

Secrets are masked. Run with the hermes-agent venv interpreter:

    ~/.hermes/hermes-agent/venv/bin/python \
        ~/.hermes/skills/own/hermes-provider-setup/scripts/voice-config-probe.py

Healthy German groq dictation: stt.mode=direct, wire=openai-multipart,
model=whisper-large-v3-turbo, language=de, api_key set. A provider without a
client wire (e.g. tts 'edge') reports mode=relay with a reason — read the
reason before calling relay broken.
"""
import json
import os
import pathlib
import sys

hermes = pathlib.Path(os.environ.get('HERMES_HOME') or pathlib.Path.home() / '.hermes')

env_file = hermes / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

os.environ.setdefault('HERMES_HOME', str(hermes))
sys.path.insert(0, str(hermes / 'hermes-agent'))

from tools.voice_client_config import resolve_client_voice_config  # noqa: E402


def mask(node):
    if isinstance(node, dict):
        return {
            k: ('<set: %d chars>' % len(v) if k == 'api_key' and isinstance(v, str) else mask(v))
            for k, v in node.items()
        }
    return node


print(json.dumps(mask(resolve_client_voice_config()), indent=2, ensure_ascii=False))
