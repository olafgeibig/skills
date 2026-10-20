#!/usr/bin/env python3
"""Shrink a Model2Vec model by pruning its Unigram vocabulary.

Keeps every token a corpus actually uses, fills the rest with the
highest-scoring Latin-script tokens, and slices the embedding table to match.
Non-Latin scripts are dropped (they become [UNK]); for a German/English corpus
the result is embedding-identical on Latin text.

Usage:
  python prune-model2vec-vocab.py --source ~/models/potion-multilingual-128M \
      --out ~/models/potion-multilingual-45k --target 45000 \
      --corpus '~/vaults/akademeia/**/*.md'

Requires a venv with tokenizers, safetensors, numpy (no torch), e.g.
  python3 -m venv m2v && m2v/bin/pip install tokenizers safetensors numpy
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import Counter

import numpy as np
from safetensors.numpy import load_file, save_file
from tokenizers import Tokenizer

# scripts a Latin-script vault never needs; anything here is dropped
DROP_RANGES = [
    (0x0370, 0x03FF), (0x0400, 0x04FF), (0x0530, 0x058F), (0x0590, 0x05FF),
    (0x0600, 0x06FF), (0x0700, 0x074F), (0x0900, 0x097F), (0x0980, 0x09FF),
    (0x0A80, 0x0AFF), (0x0B80, 0x0BFF), (0x0C00, 0x0C7F), (0x0D00, 0x0D7F),
    (0x0E00, 0x0E7F), (0x0E80, 0x0EFF), (0x10A0, 0x10FF), (0x1100, 0x11FF),
    (0x1780, 0x17FF), (0x1E00, 0x1EFF), (0x2E80, 0x2FFF), (0x3000, 0x30FF),
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF), (0xFB00, 0xFDFF), (0xFE70, 0xFEFF), (0xFF00, 0xFFEF),
    (0x10000, 0x10FFFF),
]
ALLOW = {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x00A0,
         0x00AB, 0x00BB, 0x2192, 0x25B8, 0x2500, 0x2022, 0x2605, 0x00B7}


def latin_ok(token: str) -> bool:
    for ch in token:
        cp = ord(ch)
        if cp < 0x0370 or cp in ALLOW:
            continue
        for lo, hi in DROP_RANGES:
            if lo <= cp <= hi:
                return False
    return True


def corpus_texts(patterns: list[str]):
    seen = 0
    for pat in patterns:
        for path in glob.glob(os.path.expanduser(pat), recursive=True):
            if "/.turbovault/" in path or "/.obsidian/" in path or "/.git/" in path:
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            text = re.sub(r"(?s)^---\n.*?\n---\n", " ", text)      # frontmatter
            text = re.sub(r"(?s)```.*?```", " ", text)             # code fences
            seen += len(text)
            yield text
    print(f"corpus: {seen/1e6:.2f} MB of text")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Model2Vec model directory to shrink")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--target", type=int, default=45000, help="vocabulary size to keep")
    ap.add_argument("--corpus", action="append", required=True,
                    help="glob of text files the model must cover (repeatable)")
    args = ap.parse_args()

    src = os.path.expanduser(args.source)
    out = os.path.expanduser(args.out)
    tok = Tokenizer.from_file(f"{src}/tokenizer.json")
    vocab = json.load(open(f"{src}/tokenizer.json"))["model"]["vocab"]
    emb = load_file(f"{src}/model.safetensors")["embeddings"]
    assert emb.shape[0] == len(vocab), (emb.shape, len(vocab))
    tok2id = {t: i for i, (t, _) in enumerate(vocab)}
    print(f"source: {len(vocab):,} tokens, embeddings {emb.shape} {emb.dtype}")

    counts: Counter[str] = Counter()
    batch: list[str] = []
    for text in corpus_texts(args.corpus):
        batch.append(text[:400_000])
        if len(batch) >= 64:
            for enc in tok.encode_batch(batch):
                counts.update(enc.tokens)
            batch = []
    if batch:
        for enc in tok.encode_batch(batch):
            counts.update(enc.tokens)
    print(f"corpus used {len(counts):,} distinct tokens")
    if not counts:
        raise SystemExit("corpus produced no tokens — check --corpus")

    keep: list[int] = []
    seen: set[int] = set()

    def add(i: int) -> None:
        if i not in seen:
            seen.add(i)
            keep.append(i)

    for special in ("[PAD]", "[UNK]", "<s>", "</s>", "<pad>", "<unk>"):
        if special in tok2id:
            add(tok2id[special])
    for token in sorted(counts, key=lambda t: -counts[t]):
        if token in tok2id:
            add(tok2id[token])
    corpus_kept = len(seen)
    for i, (t, _s) in sorted(enumerate(vocab), key=lambda kv: -kv[1][1]):
        if len(seen) >= args.target:
            break
        if i not in seen and latin_ok(t):
            add(i)
    print(f"kept {corpus_kept:,} corpus tokens, padded to {len(keep):,} with common Latin tokens")

    os.makedirs(out, exist_ok=True)
    tj = json.load(open(f"{src}/tokenizer.json"))
    tj["model"] = dict(tj["model"])
    tj["model"]["vocab"] = [[vocab[i][0], float(vocab[i][1])] for i in keep]
    json.dump(tj, open(f"{out}/tokenizer.json", "w"), ensure_ascii=False)

    new_emb = np.ascontiguousarray(emb[keep])
    save_file({"embeddings": new_emb}, f"{out}/model.safetensors")
    for name in ("config.json", "modules.json", "special_tokens_map.json", "tokenizer_config.json"):
        path = f"{src}/{name}"
        if os.path.exists(path):
            json.dump(json.load(open(path)), open(f"{out}/{name}", "w"), indent=1, ensure_ascii=False)
    with open(f"{out}/vocab.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(vocab[i][0] for i in keep) + "\n")

    print(f"wrote {out}: {len(keep):,} tokens, {new_emb.nbytes/1e6:.1f} MB table")
    print("verify: drop this directory into a TurboVault model_path and run vector_search_reindex")


if __name__ == "__main__":
    main()
