---
name: casefile
description: "Use when running a casefile project: cases, files, records."
license: MIT
metadata:
  version: "0.1.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  scope: standalone
  hermes:
    tags:
      - projects
      - knowledge-work
      - casefile
    related_skills:
      - hermes-projects
      - vault-ops
      - turbovault-use
      - vault-akademeia
---

# Casefile — Fall- und Aktenverwaltung realer Angelegenheiten

Projektkind (Kind) für Knowledge-Work-Projekte, in denen reale Angelegenheiten betreut werden: Pflege, Gesundheit, Verträge, Nachlass, Haus, Behörden. Kernartefakt ist die **Fallakte** aus Vorgängen, Akten und Stammdaten — nicht Code, nicht ein einzelnes Deliverable. Der Vorgang endet, die Akte nie.

## When to Use

- Ein Projekt sammelt und betreut Fakten, Dokumente, Vorgänge und Aufgaben zu realen Personen oder Sachen
- Ein neues casefile-Projekt aufsetzen oder ein bestehendes umstellen
- Eine Note in einem casefile-Projekt klassifizieren, anlegen oder pflegen
- Einen Vorgang beginnen, fortschreiben oder schließen

Nicht für Reise-Projekte (`travel-planning`), Deliverable-Arbeit (`authoring-vault`) oder Code-Projekte (`hermes-projects`).

## Die sechs Dokumentenklassen

**Klasse = Ordner + Frontmatter `type:`.** Die Klasse entscheidet den Ablageort und die Pflege — nicht das Thema. Die Werte stehen in der `type:`-Tabelle der Vault-Root-`AGENTS.md` mit Kind-Zuordnung; diese Tabelle hier ist die Spec.

| Klasse | `type:` | Testfrage | Pflege | Ablage |
|---|---|---|---|---|
| Vorgang | `vorgang` + `status: offen/ruht/geschlossen` | Kann ich das schließen? | `## Stand` in-place, `## Verlauf` angehängt (neuester zuerst) | `vorgaenge/<YYYYMMDD Anlass>/` |
| Arbeitsergebnis | `arbeitsergebnis` | Ist es einmal erzeugt? | unverändert lassen (Beweischarakter) | im Ordner seines Vorgangs |
| Akte | `akte` | Endet das je? | `## Stand` in-place, `## Verlauf` angehängt | `akten/` |
| Stammdatum | `stammdatum` | Schlage ich das nach? | Werte in-place ersetzen, keine Historie | `stammdaten/` |
| Ressource | `resource` | Unveränderte Fremdkopie? | nie anfassen, Herkunft notieren | Roh-Ordner des Projekts |
| Utility | `utility` | Ist es ein Werkzeug für mich? | bei Bedarf | Root oder `utility/` |

**Doppel-Ledger vermeiden:** Die Akte trägt pro Ereignis eine Zeile mit Link auf den Vorgang; der ausführliche Verlauf lebt nur im Vorgang. Dasselbe zweimal zu erzählen heißt, es später zweimal halb zu schreiben.

## Vorgang

- Ordner `vorgaenge/<YYYYMMDD Anlass>/`; der MoC heißt `+<Ordnername>` und trägt `type: vorgang` plus `status: offen|ruht|geschlossen`.
- Abschnitte: `## Stand` → `## Verlauf` (`### YYYY-MM-DD`, neuester zuerst) → `## Arbeitsergebnisse` (Links) → `## Offen` (Tasks mit stabiler ID und Action-Tag).
- Stand und Verlauf leben in einer Note zusammen, **weil der Vorgang endet**; die Akte hält sie getrennt, weil sie nie endet.
- Datumspräfix des Ordners = Anfang (Datum des ältesten Belegs bei unbekanntem Start), nicht „gehört zu".
- Geschlossene Vorgänge bleiben mit `status: geschlossen` liegen; kein Umzug ins `archive/`.
- Briefe, Fragenkataloge, Entwürfe und Belege werden verlinkt, nicht im Vorgang dupliziert.

## Personen-Achse

Personen laufen über **Tags und Dateinamen**, nie über Ordner — ein Personen-Ordner schneidet die Klassen-Achse.

- Jede personenbezogene Note trägt den Personennamen im Dateinamen; Tags pro Person plus Projekt-Tag.
- Gemeinsame Fakten explizit als „gemeinsam" labeln oder in eine eigene Sammel-Note legen.
- Der Router hält eine Kurzkarte je Person: Name, Geburtsdatum (Disambiguator), ein Status-Stichwort, Link in die Akte — keine Zustandsdetails, sonst zweite Quelle.
- Konkrete Verwechslungsfallen (Vollmachten, Kassen, ähnlich benannte Verträge) notiert die Projekt-`AGENTS.md` als Sperre — das ist Projektwissen.

## Navigation

- Dach-MoC `+<projekt>.md` (`type: moc`) routet statt zu inventarisieren: Personen-Kurzkarte, „Aktive Vorgänge" (Tabelle Vorgang / Stand / nächster Schritt / Frist), „Akten", „Stammdaten", „Geschlossen", Tasks-Query.
- `topics:` zeigt auf den eigenen Vorgangs-MoC (Arbeitsergebnisse) bzw. den Dach-MoC; der Body-Footer `Topics:` spiegelt es.
- Keine zweiten Inventarlisten — was existiert, führt der Vorgangs-MoC bzw. der Router.

## Setup eines neuen casefile-Projekts

1. `projects/<x>/` anlegen mit `+<x>.md` (Router) und `AGENTS.md` (Projektfakten, Abweichungen, Verweis auf diesen Skill).
2. Klassen-Ordner erst beim ersten Beleg anlegen, nicht auf Vorrat.
3. Eintrag in `projects/INDEX.md` plus reziproker Zeiger aus der thematischen Area — beide Suchpfade müssen landen.
4. Personen-Kurzkarte und Tasks-Query in den Router. Ein `project-<x>`-Skill entsteht erst, wenn eine wiederkehrende Methode da ist.

## Betrieb mit TurboVault

- `type`, `status`, Tags via `update_frontmatter`/`manage_tags`; Klassen- und Personen-Queries via `query_frontmatter_sql` (pfad-scoped, `tags`-Join).
- Vorgang anlegen via `write_note`/`CreateNote` aus dem Template; Beweissicherung, Duplikat-Auflösung und Löschungen über `audit_log` + `rollback_note` — destructive Ops mit `on_backlinks: refuse`, Transaction-ID in den Report.
- Nachprüfung: `yaml.safe_load` über den Frontmatter-Block, `graph_report(kind="broken_links")` und der Note-Check des jeweiligen Vault-Skills; Link-Reste nach Umbenennungen per Rohtext-Suche (Mechanik und Grund: `turbovault-use`).

## Pitfalls

- Nie zwei Schreib-Operationen parallel auf dieselbe Datei und tote Links per Rohtext-Suche statt SQL suchen — beide Regeln mit Grund im Skill `turbovault-use`.
- Nie zwei Notizen desselben Sachverhalts (Doppel-Ledger), nie eine Status-Historie in einer Daten-Note.
- Telefonisches ist Aussage der sprechenden Person, kein Befund; Roh-Importe nie glätten oder „verbessern".
- Keine neuen `type:`-Werte ad hoc im Projekt — Werte sind Kind-Sache und brauchen ihren Zeiler in der Vault-Tabelle.
- Keine Personen-Ordner und keine dritte Ordnerachse pro Person.

## Verification

- Jede Note trägt genau eine Klasse (`type:`) und liegt im passenden Ordner.
- Jeder Vorgangs-MoC hat `status:` und alle vier Abschnitte; Arbeitsergebnisse sind verlinkt, nicht kopiert.
- `topics:` und Footer spiegeln sich; der Graph zeigt keine neuen Broken Links.
- Nach jedem Verschieben oder Umbenennen: Rohtext-Sweep auf alte Pfade und Altnamen.
