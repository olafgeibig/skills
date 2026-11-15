---
description: Alle offenen Aufgaben für {{Projekt}} — aus allen Fällen und Dossiers
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
     Erledigtes wird nicht hier gesammelt: was ein Meilenstein war, steht in der Chronologie. -->

```tasks
not done
path includes projects/{{x}}
sort by priority
```
