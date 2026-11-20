# Search a Dossier Project

Use `scripts/search.py` from the skill directory. It reads Markdown locally, uses only the Python standard library and never changes notes. Read knowledge notes before opening full evidence unless the claim itself needs checking.

```bash
python3 scripts/search.py topic <project> --query 'Gebühren Frist' --type case,analysis
python3 scripts/search.py similar <project> --note 'Beispielfall'
python3 scripts/search.py chain <project> --note 'cases/Beispielfall.md' --json
python3 scripts/search.py calibrate <project> --questions eval-questions.json --limit 5
```

- `topic` requires lexical overlap with title, description, body or the curated head; `similar` requires textual overlap and defaults to the reference note's type. Ranking signals are not evidence. Inspect the heads, then verify in the cited note or original.
- `--note` accepts a unique basename or exact project-/vault-relative path. `chain` shows frontmatter and body edges separately, retaining the original URL, anchor and label. It is a local trace, not a vault-wide link-health check.
- `calibrate` compares predefined weight sets against a nonempty JSON list such as `[{"q":"Gebühren Frist","expect":["Beispielfall"]}]`. Use expected basenames. It reports hit rate and mean reciprocal rank at `--limit`; it does not rewrite defaults. Use `--weights` with a JSON object of finite nonnegative signal weights to override defaults in queries.
- Use `--json` for machine-readable results. An empty hit list means no candidate matched, not that the underlying claim is false or the vault lacks the evidence.
