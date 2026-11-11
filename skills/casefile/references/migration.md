# Migration eines bestehenden Projekts in die Klassenstruktur

Wann: ein bestehendes casefile-Projekt, dessen Notizen flach im Projektordner liegen und einheitlich `type: zettel` tragen, soll auf die sechs Klassen umgestellt werden. Das ist eine Strukturmaßnahme mit festem Ablauf, keine Note-für-Note-Pflege.

Nicht verwechseln: eine **Modelländerung** — die Shape der Klassen selbst ändert sich (Akte ohne eigenen Verlauf, Zeitleiste nur noch Meilensteine) und ein schon klassifiziertes Projekt zieht nach — ist eine eigene Maßnahme mit eigenem Ablauf, siehe unten.

Vor dem ersten Schritt stehen **Klassenzuordnung, Ordnernamen und Root-Ausnahmen** fest. Ziel ist nicht „alles in Ordner", sondern: jede Note hat genau eine Klasse im passenden Ordner, und jede Root-Ausnahme ist eine begründete Entscheidung.

## Ablauf

1. **Inventar erheben (Baseline).** Dateiliste mit `type:` je Note; alle `[[Ziele]]` aus Rohtext gegen eine Map aus Dateistämmen und Vault-relativen Pfaden aufgelöst (Unauflösbare notieren, nicht fixen); `topics`-/Footer-Abgleich je Note. Die Zahlen — unauflösbare Ziele im Projekt und die vaultweite Broken-Link-Zahl (`get_vault_context`/`graph_report`) — sind die Baseline der Abschlussprüfung. Bei großem Projekt zuerst die Link-Kosten messen, siehe Skill `vault-ops` (Refactoring-Workflows).
2. **Entscheidungen treffen, bevor etwas wandert.** Ordnernamen der Klassen in der Projektsprache (deutsch z. B. `akten/`, `stammdaten/`, `vorgaenge/`, `quellen/`); welche Notizen am Root bleiben dürfen (Router, Utility, projektweite Zeitachse) — jede Ausnahme mit Begründung, beide wandern in die Projekt-`AGENTS.md`; Benennung der Vorgangs-MoCs (`+<Ordnername>`, also MoC-Name = Ordnername). Uneindeutige Klassenzuordnungen hier klären, nicht während des Umzugs.
3. **Verschieben zuerst, Inhalt nie anfassen.** Eine `move_file`/`move_note` je Note in den Klassenordner; parallel über verschiedene Dateien, nie zwei Writes auf dieselbe Datei. Ordner entstehen hier mit dem ersten Beleg, nicht auf Vorrat.
4. **Frontmatter je Note setzen:** Klasse als `type:`, `topics` auf den zuständigen Vorgangs-MoC bzw. Router, Vorgangs-Notizen zusätzlich `status:`. Eine Note ohne Frontmatter bekommt es beim Verschieben — sonst wandert sie unregistriert an den neuen Ort.
5. **Links reparieren, beide Sorten.** Verschobene Notizen brechen **pfadqualifizierte** Links (`[[projekt/x/Name]]`), umbenannte brechen **bare-name** Links (`[[Alt]]` → `[[Neu]]`). Rohtext-Sweep auf Altname und alten Pfad; nie SQL (die `links`-Tabelle verwirft unauflösbare Ziele). Pfadlinks dabei in bare-name Wikilinks umstellen — die überleben den nächsten Ordnerwechsel.
6. **Vorgangs-MoCs anlegen** (`type: vorgang`, `status: offen|ruht|geschlossen`, Abschnitte Stand / Verlauf / Arbeitsergebnisse / Offen) und Router-MoC als Tabelle neu aufsetzen (Vorgang / Stand / nächster Schritt), nicht als Inventarliste.
7. **Feinarbeit:** fehlende `Topics:`-Footer per `write_note(mode=append)` ergänzen, ohne den Body anzufassen; `updated:` setzen; Projekt-`AGENTS.md` um die neuen Regeln fortschreiben (Ordnernamen, Root-Ausnahmen, offene Splits).
8. **Abschlussprüfung gegen die Baseline — alle vier Punkte müssen passen:** (a) jede Note hat genau eine Klasse im passenden Ordner; (b) `topics` und Footer spiegeln sich zeilengenau; (c) der Resolver findet 0 unauflösbare Ziele im Projekt; (d) die vaultweite Broken-Link-Zahl ist unverändert. Erst dann hat die Migration keine Kollateralschäden außerhalb des Projekts hinterlassen.

## Pitfalls

- **Migration ist kein Moment für inhaltliche Splits.** Steht eine Akte inhaltlich zwischen zwei Klassen (Vorgangsabschnitte in einer Akte), wird das als offener Punkt dokumentiert und im eigenen Auftrag gelöst — im Umzugsschritt vermischen sich sonst Struktur- und Textarbeit und der Diff wird unprüfbar.
- **Identifikatoren nie „reparieren", weil sie im Output seltsam aussehen.** Tool-Output kann Tokens mittig maskieren; das ist Anzeige, nicht Dateiinhalt. Vor jeder Namenskorrektur die echten Bytes per Exact-Match prüfen (`turbovault-use` → Verification).
- **Verschoben ist nicht fertig:** erst die Prüfung gegen die Baseline schließt die Migration ab. Der Baum kann sauber aussehen und trotzdem tote Links tragen, wenn nur eine der beiden Linksorten aus Schritt 5 repariert wurde.

## Modelländerung durch ein bestehendes Projekt ziehen

Wann: die Klassen-Shape selbst ändert sich (etwa Akte ohne eigenen Verlauf, Zeitleiste nur noch Meilensteine) und ein **schon klassifiziertes** Projekt soll nachziehen. Anders als die Klassenmigration wandert hier nichts — die Notizen bleiben an ihrem Ort, ihre **Form** ändert sich.

1. **Spec zuerst, dann Daten.** Die geänderten Regeln zuerst in den Skill und die Klassen-Tabelle schreiben, danach die Notizen — sonst entstehen mitten im Lauf wieder Notizen nach dem alten Muster. Ändert dieselbe Regel mehrere Ebenen (generische Spec, Vault-Form, Projekt-Handbuch), alle in einem Durchgang **vor** der ersten Notiz.
2. **Notizen in der Reihenfolge ihrer Abhängigkeit umschreiben:** Akten (Abschnitte auf die neue Form) → herausgelöste Werte in die Stammdaten (neues Stammdatum anlegen, in den Router einhängen, Werte **verschieben**, nicht kopieren) → Zeitleiste (Aufnahmeregeln anwenden; jeder Link zeigt auf die Notiz, die den Fakt trägt — Akte für geltenden Zustand, Vorgang für den Weg) → Vorgänge (aufgenommene Aufgaben, korrigierte Pointer) → Router-MoC (Zeilen an die neuen Notiz-Scope anpassen, `updated:` überall mitziehen).
3. **Aufgaben mit stabiler ID sind Umzugsgut.** Wandert eine Aufgabe zwischen Notizen, zeigen im selben Durchgang alle Verweise auf ihre ID — Rohtext-Sweep auf die ID, nicht nur auf Notiznamen. Ein Prosa-Pointer („Aufgabe … in [[Note]]") ist nach dem Umzug ein toter Pfad und wird in eine echte Task mit ID und Action-Tag überführt.
4. **Vorräte mitnehmen.** Leere Stub-Notizen und Router-Waisen (`validate_vault`, Notiz ohne MoC-Eintrag) finden und einhängen — eine Umstellung, die nur die geplanten Notizen bearbeitet, lässt die toten Ecken toter und der nächste Lauf hält sie für erledigt.
5. **Abschlussprüfung wie Schritt 8**, plus: Zeilen-/Eintragszählung vorher und nachher muss plausibel aufgehen (entfernte Einträge sind im Vorgang belegt oder als Meilenstein geblieben). **Bewusst liegengelassenes im Report nennen** — Inhalt, der erst bei einem künftigen Vorgang einzieht, und Task-Ketten, die an Abhängigkeiten hängen; sonst sieht der nächste Lauf die Lücke als Defekt.

### Pitfalls zur Modelländerung

- **Keine Vermischung mit der Klassenmigration.** Läuft beides in einem Projekt, zuerst die Form ändern (oben), dann verschieben — ein Umzug, der gleichzeitig Form und Ort ändert, macht den Diff unprüfbar (dieselbe Regel wie oben, andere Richtung).
- **Spec-Stand direkt vor dem Patch neu lesen.** Ein mitarbeitender Schreiber (Review-Fork, Cron) kann die Spec zwischen Lesen und Schreiben geändert haben; eine Variante, die der gerade entschiedenen Form widerspricht, wird bewusst überschrieben statt gemergt (`concurrent-write-coordination`) — Attribution an den User geht dem Überschreiben voraus.
