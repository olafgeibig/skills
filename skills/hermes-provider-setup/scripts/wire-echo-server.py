#!/usr/bin/env python3
"""Wire echo server: captures the exact request body Hermes sends to a provider.

Usage: wire-echo-server.py [port] [log_path]
  port     default 8765
  log_path default <scratch>/wire-req-body.json

Pair it with a temporary providers.<key> entry whose base_url points at
http://127.0.0.1:<port>/v1 (see references/request-wire-probes.md), then read
the captured body instead of guessing from transport code.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = os.environ.get("WIRE_LOG") or os.path.join(
    os.environ.get("TMPDIR") or "/tmp", "wire-req-body.json"
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw)
        except Exception:
            body = {"_raw": raw.decode("utf-8", "replace")}
        body["_headers"] = {
            k: v for k, v in self.headers.items()
            if k.lower() in ("authorization", "content-type")
        }
        with open(LOG, "w") as f:
            json.dump(body, f, indent=2)
        model = body.get("model", "wire-echo")
        msg = {"role": "assistant", "content": "wire-echo-ok"}
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in ((msg, None), ({}, "stop")):
                chunk = {
                    "id": "wire1", "object": "chat.completion.chunk", "created": 0,
                    "model": model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            out = {
                "id": "wire1", "object": "chat.completion", "created": 0, "model": model,
                "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            data = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    if len(sys.argv) > 2:
        LOG = sys.argv[2]
    print(f"capturing to {LOG} on 127.0.0.1:{port}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
