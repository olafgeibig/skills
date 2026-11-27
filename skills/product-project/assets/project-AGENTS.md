# <Project Name> — Projektkontext

## Zweck

<!-- Kurzbeschreibung: Welches Produkt / welche Lösung wird hier entwickelt und dokumentiert? -->

## Setup

- Projektform: `vault`
- Projekttyp: `product-project`
- Containertyp: `vault`
- Case-Präfix (`case_prefix`): `<PREFIX>` (z. B. `PRJ` → `PRJ-001`)
- Projektverzeichnis: dieses Verzeichnis (`projects/<x>/`) — diese Datei ist das Betriebshandbuch.
- Sprache: Deutsch / Englisch (Schema-Werte Englisch; Titel, Überschriften und Fließtext nach Projektvorgabe)
- Pflicht-Skills: `hermes-projects`, `product-project`, `vault-ops`, `turbovault-use`

## Wichtige Ressourcen

- [[+<X>]] — Haupteinstieg (Project Knowledge und Case Knowledge)
- [[Aufgaben <X>]] — Projektaufgaben
- [[Chronologie <X>]] — Meilensteine
- [[Bookmarks <X>]] — Externe Links und Ressourcen (optional)
- [[KB Log <X>]] — Änderungsprotokoll der Knowledge Base
<!-- Optional: Verweis auf verknüpftes cs-project oder externes Repo (mit Zugriffsregel) -->

## Regeln

- Keine Veröffentlichung aus diesem Projekt heraus (Notizen sind das Ergebnis).
- **Project Knowledge** (`knowledge/raw/`, `distilled/`, `kb/`, `masterdata/`, ohne `case_id`-Präfix) bleibt strikt getrennt von **Case Knowledge** (`cases/`, `activities/`, `artifacts/`, `product/` mit `case_id:`).
- `knowledge/masterdata/` gehört dem User (Lookup-Werte nur auf explizite Anweisung ändern, keine Checkboxes).
- Kalibriertes Review-Gate: Substanzielle Agent-Edits an `knowledge/kb/`-Fakten landen als `status: draft`; rein additive Quellenbestätigungen in `## Quellen` / `## Citations` + `as_of`-Bump erhalten `reviewed` + `reviewed_on`.
- Quellen stehen einheitlich im Body unter `## Quellen` (bzw. `## Citations` in englischen Projekten) mit Obsidian `[[Wikilinks]]`.
- `archive/` wird in der Suche (`exclude_paths: ["archive/"]`) und in SQL (`AND path NOT LIKE 'projects/<x>/archive/%'`) ausgeschlossen.
- Keine Geheimnisse oder Zugangsdaten in Notizen.

<!-- Optionale Projekt-Hooks (bei Bedarf einkommentieren und konkretisieren):
- KB-Promotionskriterien: Was darf über die Standardregeln hinaus per Promote to KB nach knowledge/kb/ übernommen werden oder ist ausgeschlossen?
- Verifikations-Gates: Wann soll Tier-2 Grounding oder ein Constraint-Check zusätzlich erzwungen/entspannt werden (z. B. jedes analysis, jede evaluation)? -->

## Regeln erweitern

Regeln, die über eine Seite hinauswachsen, gehören in `conventions.md` (erst anlegen, wenn benötigt, und hier verlinken).
