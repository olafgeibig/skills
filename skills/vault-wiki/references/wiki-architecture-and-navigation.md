# Wiki Architecture and Navigation

## Directory model

```text
vault-root/
└── wiki/
    ├── index.md
    ├── domain-one/
    │   ├── SCHEMA.md
    │   ├── domain-one-wiki.md
    │   ├── log.md
    │   ├── raw/
    │   │   ├── articles/
    │   │   ├── papers/
    │   │   ├── transcripts/
    │   │   └── assets/
    │   ├── entities/
    │   ├── concepts/
    │   ├── comparisons/
    │   └── queries/
    └── domain-two/
```

The root `wiki/index.md` is the hub. Each domain is a direct child of `wiki/` and has its own schema, index, and log.

- Layer 1: immutable raw source material.
- Layer 2: agent-maintained wiki pages.
- Layer 3: domain rules in `SCHEMA.md`.

## Hub

Each hub section links to one domain index and provides a concise routing abstract:

```markdown
## [[wiki/ai-research/ai-research-wiki|ai-research]]
AI and machine-learning research, models, papers, and benchmarks.
```

Do not add page counts, tag inventories, or last-update dates to the hub. Those belong in domain indexes or logs.

A domain wiki is not initialized until it is registered in the hub.

## Routing

Use this order:

1. If the user names a domain, use it.
2. Otherwise match the request or source against hub abstracts.
3. If more than one domain remains plausible, ask rather than guess.

The hub abstracts are routing information. Keep them accurate as domain scope changes.

## Session orientation

For an existing domain:

1. read `wiki/index.md`;
2. select the domain;
3. read `wiki/<domain>/SCHEMA.md`;
4. read `wiki/<domain>/<domain>-wiki.md`;
5. read the recent portion of `wiki/<domain>/log.md`;
6. for large domains, run a path-scoped search before creating content.

This prevents duplicate pages, schema violations, missed cross-references, repeated work, and writes to the wrong domain.

## Wikilinks

Use full vault paths for every wiki link:

```text
[[wiki/<domain>/<type>/<page-name>]]
```

Examples:

```text
[[wiki/ai-research/concepts/llm-infrastructure]]
[[wiki/ai/entities/andrei-karpathy|Andrej Karpathy]]
```

Do not use `[[concepts/page]]` or omit the `wiki/` prefix. Relative-looking wiki paths resolve inconsistently from nested pages and can appear as broken links.

Link directly across domains. Do not create adapter pages or duplicate content merely to avoid a cross-domain link.

## Navigation maintenance

After creating, moving, archiving, or deleting a page:

- update the domain index;
- update the action log;
- verify forward links and backlinks;
- run broken-link checks;
- refresh the hub abstract if domain scope changed.
