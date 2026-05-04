#!/usr/bin/env python3
"""
Lint a domain wiki for broken links, low outbound links, and orphans.
Usage: python3 lint_wiki.py --wiki /path/to/wiki [--domain domain-name]
"""

import argparse
import os
import re
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Lint wiki for broken links and outbound issues."
    )
    parser.add_argument("--wiki", required=True, help="Path to wiki root directory")
    parser.add_argument("--domain", help="Scope to specific domain (e.g. rlm, erbe)")
    args = parser.parse_args()

    WIKI = os.path.abspath(args.wiki)
    DOMAIN = args.domain

    # Build valid targets
    valid = {}
    for root, dirs, files in os.walk(WIKI):
        for f in files:
            if f.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, f), WIKI).replace(".md", "")
                valid[rel] = 1

    wiki_dirs = ["entities", "concepts", "comparisons", "queries"]
    broken = []
    low_out = []

    domains = [DOMAIN] if DOMAIN else os.listdir(WIKI)

    for wiki_name in domains:
        wiki_path = os.path.join(WIKI, wiki_name)
        if not os.path.isdir(wiki_path) or wiki_name in ("_archive",):
            continue
        for wd in wiki_dirs:
            wd_path = os.path.join(wiki_path, wd)
            if not os.path.isdir(wd_path):
                continue
            for fname in os.listdir(wd_path):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(wd_path, fname)
                with open(fpath) as f:
                    content = f.read()
                links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
                outbound = []
                for link in links:
                    if link.startswith(("http://", "https://", "ftp://", "raw/")):
                        continue
                    if link.startswith(wiki_name + "/"):
                        target = link
                    else:
                        target = wiki_name + "/" + wd + "/" + link
                    if target not in valid:
                        broken.append((fpath.replace(WIKI + "/", ""), link))
                    else:
                        outbound.append(target)
                real = [t for t in outbound if not t.startswith("raw/")]
                if len(real) < 2:
                    low_out.append(
                        (fpath.replace(WIKI + "/", ""), len(real), list(set(real))[:5])
                    )

    # Orphans
    inbound = {}
    for wiki_name in domains:
        wiki_path = os.path.join(WIKI, wiki_name)
        if not os.path.isdir(wiki_path):
            continue
        for wd in wiki_dirs:
            wd_path = os.path.join(wiki_path, wd)
            if not os.path.isdir(wd_path):
                continue
            for fname in os.listdir(wd_path):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(wd_path, fname)
                with open(fpath) as f:
                    content = f.read()
                links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
                for link in links:
                    if link.startswith(("http://", "https://", "ftp://", "raw/")):
                        continue
                    if link.startswith(wiki_name + "/"):
                        target = link
                    else:
                        target = wiki_name + "/" + wd + "/" + link
                    inbound.setdefault(target, []).append(fpath.replace(WIKI + "/", ""))

    orphans = []
    for wiki_name in domains:
        wiki_path = os.path.join(WIKI, wiki_name)
        if not os.path.isdir(wiki_path):
            continue
        for wd in wiki_dirs:
            wd_path = os.path.join(wiki_path, wd)
            if not os.path.isdir(wd_path):
                continue
            for fname in os.listdir(wd_path):
                if not fname.endswith(".md"):
                    continue
                rel = wiki_name + "/" + wd + "/" + fname.replace(".md", "")
                if rel not in inbound or len(inbound[rel]) == 0:
                    orphans.append(rel)

    print(f"Broken links : {len(broken)}")
    print(f"Low outbound : {len(low_out)}")
    print(f"Orphans     : {len(orphans)}")
    print()

    if broken:
        print("=== BROKEN LINKS ===")
        for f, l in sorted(broken):
            print(f"  [[{l}]]  ->  {f}")
        print()

    if low_out:
        print("=== LOW OUTBOUND (< 2 non-raw) ===")
        for f, cnt, links in sorted(low_out):
            print(f"  [{cnt}] {f}")
            for l in links:
                print(f"       -> [[{l}]]")
        print()

    if orphans:
        print("=== ORPHANS (no inbound links) ===")
        for o in sorted(orphans):
            print(f"  {o}")
        print()

    if not broken and not low_out and not orphans:
        print("All checks passed.")


if __name__ == "__main__":
    main()
