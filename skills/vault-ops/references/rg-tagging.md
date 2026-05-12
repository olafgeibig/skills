## Tag Discovery & Taxonomy
On‑demand discovery; prefer existing tags; create new ones only if needed.

Quick commands:

```bash
rg -No -P '(?<!\w)#([A-Za-z0-9/_-]+)' . -r '$1' | sort -u
rg -No '^[\t ]*tags:[\t ]*\[[^\]]*\]' . -g '!**/.obsidian/**' -r '$0' | sed -E 's/.*\[|\].*//; s/["\'\' ]//g; s/,/\n/g' | sed '/^$/d' | sort -u
rg -No -U 'tags:[\t ]*\n(?:[\t ]*-\s*[A-Za-z0-9/_-]+\s*\n)+' . | rg -No '[A-Za-z0-9/_-]+' | sort -u
```
