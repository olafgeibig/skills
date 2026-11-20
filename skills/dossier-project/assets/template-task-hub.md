---
description: Alle offenen Aufgaben für {{Projekt}} — aus den Fällen
type: utility
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
tags:
- project/{{x}}
topics:
- '[[+{{Projekt}}]]'
---

# Aufgaben — {{Projekt}}

<!-- KOPF: Die EINE Query des Projekts. Der Router rendert sie nicht noch einmal,
     sondern zeigt hierher. Am Projekt-Root, nicht in einem Ordner.
     Erledigtes wird nicht hier gesammelt: was ein Meilenstein war, steht in der Chronologie.
     Nur cases/ ist eine Aufgabenquelle. {{Projektpfad-RegEx}} steht für den
     vault-relativen Projektpfad, Regex-Zeichen und Schrägstriche maskiert. -->

```tasks
not done
path regex matches /^{{Projektpfad-RegEx}}\/cases\//
sort by priority
```
