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

- [[+<X>]] — Haupteinstieg (Knowledge Base und Cases)
- [[Aufgaben <X>]] — Projektaufgaben
- [[Chronologie <X>]] — Meilensteine
- [[Bookmarks <X>]] — Externe Links und Ressourcen (optional)
- [[KB Log <X>]] — Änderungsprotokoll der Knowledge Base
<!-- Optional: Verweis auf verknüpftes cs-project oder externes Repo (mit Zugriffsregel) -->

## Regeln

- Keine Veröffentlichung aus diesem Projekt heraus (Notizen sind das Ergebnis).
- Zeitloses Wissen gehört in `knowledge/` (ohne Case-ID-Präfix); fallbezogene Meetings, Mails und Analysen gehören in `activities/` mit `case_id:`.
- `knowledge/kb/`-Fakten landen nach Agent-Edits immer als `status: draft`; nur menschliche Freigabe setzt `status: reviewed` + `reviewed_on:`.
- `archive/` wird in der normalen Suche ausgeschlossen (`exclude_paths: ["archive/"]`) und nur auf explizite Anfrage gelesen.
- Keine Geheimnisse oder Zugangsdaten in Notizen.

## Regeln erweitern

Regeln, die über eine Seite hinauswachsen, gehören in `conventions.md` (erst anlegen, wenn benötigt, und hier verlinken).
