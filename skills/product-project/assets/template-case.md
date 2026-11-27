---
description: Case <CASE-ID> — <ein Satz zum Thema und Ziel>
type: case
case_id: "<CASE-ID>"
case_kind: simple
status: open
updated: YYYY-MM-DD
tags:
  - project/<x>
topics:
  - "[[+<X>]]"
---

# <CASE-ID> <Titel>

<!-- case_kind: simple | complex.
     status: open | active | done | rejected (done bleibt in cases/, nie archivieren).
     Jede Datei, die zu diesem Case gehört (activities/raw/, activities/, artifacts/, product/), trägt case_id: "<CASE-ID>" im Frontmatter. -->

## Kurzfassung

<!-- Aktueller Stand in 2–4 Sätzen (wird in place aktualisiert). -->

## Ziel & Abnahmekriterien

<!-- Englisch: ## Goal & Acceptance Criteria.
     Nummerierte Liste (1., 2., ...) verwenden — keine Markdown-Checkboxes (- [ ]), sonst erfasst das Obsidian Tasks Plugin sie als Aufgaben. -->

- **Ziel:** <!-- Was soll erreicht werden? -->
- **Abnahmekriterien:**
  1. <!-- Konkretes, prüfbares Kriterium -->

<!-- Optional (on-demand / per AGENTS.md): ## Verification
| Kriterium | Urteil | Beleg |
|---|---|---|
| 1. ... | true / false / null | [[Quelle]] — "..." | -->

## Log

<!-- Handgepflegte Bulleted-Liste mit Datum und Typ (nicht automatisch generiert). Format: `- YYYY-MM-DD — **<Type>** [[Link]] — Kurzbeschreibung` (Typen: Extract, Research, Analysis, Note, Artifact, Requirement, Concept, Evaluation, Spec). Agent prüft per SQL, ob alle Dateien mit dieser case_id hier oder unter Ergebnisse verlinkt sind. -->
- YYYY-MM-DD — **Extract** [[<CASE-ID> YYYY-MM-DD Aktivität]] — Kurzbeschreibung

## Ergebnisse

<!-- Links zu artifacts/ (simple) bzw. product/ Kette (complex). -->

## Aufgaben

<!-- Offene Aufgaben, die konkret zu diesem Case gehören. -->
