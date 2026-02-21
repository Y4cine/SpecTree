Perfekt. Ich fasse dir die gewünschten Änderungen als **strukturierte Addenda-Übersicht** zusammen — so formuliert, dass:

* du sie als Backlog lesen kannst,
* eine LLM sie als präzise Änderungsanforderung versteht,
* und wir später jedes Thema einzeln in ein echtes Addendum überführen können.

Keine Code-Details, nur klare Änderungsblöcke. (Scope-Disziplin)

---

# `planned_changes.md`

**Post-MVP Feature Backlog (Structured Additions)**

---

# 0. Schema Evolution & Field Extension (Foundation)

## Ziel

Die Anwendung soll zukünftige neue Felder im Node-Schema unterstützen, ohne alte Dateien unbrauchbar zu machen.

## Anforderungen

### 0.1 Backward Compatibility

* Beim Laden dürfen fehlende Felder existieren.
* Fehlende Felder werden mit Default-Werten im Speicher ergänzt.
* `children` muss immer als Liste existieren.

### 0.2 Canonical Save

* Beim Speichern wird immer das aktuelle vollständige Schema geschrieben.
* Alte Dateien werden dadurch implizit “upgegradet”.

### 0.3 Schema-Version

* `schema_version` bleibt erhalten.
* Wenn eine Datei eine höhere Version als die App unterstützt, wird sie nur read-only geladen oder mit Warnung.

## Motivation

Ermöglicht zukünftige Felder wie `tags`, `status`, `owner`, etc., ohne Migrationschaos.

---

# 1. Multi-Instanz-Fähigkeit (Grundlage für Cross-Instance DnD)

## Ziel

Die Anwendung soll mehrfach gleichzeitig gestartet werden können.

## Anforderungen

### 1.1 Mehrfachstart erlaubt

* Es darf keine Single-Instance-Sperre geben.

### 1.2 File-Handling

Beim Öffnen derselben Datei in zwei Instanzen muss definiert sein:

* Entweder:

  * Locking (zweite Instanz read-only)
  * oder Warnung beim Speichern

MVP-Entscheidung erforderlich:

* Read-only Mode für zweite Instanz
  ODER
* Konfliktwarnung beim Speichern

## Motivation

Vorbedingung für Drag & Drop zwischen Instanzen.

---

# 2. Drag & Drop innerhalb einer Instanz

## Ziel

Nodes sollen per Drag & Drop im Tree bewegt werden können.

## Anforderungen

### 2.1 Unterstützte Aktionen

* Reorder innerhalb derselben Parent-Ebene
* Move als Child eines anderen Nodes
* Visuelle Drop-Indikation

### 2.2 Technische Regeln

* Jede DnD-Aktion muss über MoveNodeCommand laufen.
* Undo/Redo muss vollständig funktionieren.
* sort_key muss korrekt angepasst werden.

### 2.3 Einschränkungen

* Root darf nicht verschoben werden.
* Node darf nicht in eigenen Subtree verschoben werden.

## Motivation

Intuitive Baum-Manipulation.

---

# 3. Drag & Drop zwischen Instanzen

## Ziel

Nodes sollen zwischen zwei laufenden App-Instanzen verschoben oder kopiert werden können.

## MVP-Variante

Nur Copy, kein Move.

## Anforderungen

### 3.1 Transferformat

* Subtree wird als JSON-Snippet über MIME Data übertragen.

### 3.2 Zielinstanz

* Fügt Subtree als neuen Sibling oder Child ein.
* sort_key korrekt berechnen.
* Alle Nodes neu erzeugen (keine ID-Synchronisation).

### 3.3 Einschränkungen

* sensors/actuators/image werden normal übernommen (kein spezielles Handling).
* printable wird übernommen.

## Motivation

Arbeiten mit mehreren Dokumenten.

---

# 4. Kontextmenü im TreeView

## Ziel

Kontextabhängige Aktionen per Rechtsklick.

## Menüeinträge

* Add Child
* Add Sibling (above)
* Add Sibling (below)
* Delete
* Move Up
* Move Down
* Flatten
* Expand

## Anforderungen

* Alle Aktionen müssen Commands verwenden.
* Kontextmenü darf keine direkte Modelmanipulation durchführen.

## Motivation

Schnellere Bedienung ohne Toolbar.

---

# 5. Erweiterte Shortkeys + Hints

## Ziel

Tastatursteuerung fördern.

## Anforderungen

### 5.1 Shortkeys

* Ctrl+Z Undo
* Ctrl+Y / Ctrl+Shift+Z Redo
* Ctrl+S Save
* Del Delete
* Optional:

  * Ctrl+Shift+Up/Down Move
  * Ctrl+Enter Add Sibling

### 5.2 Sichtbarkeit

* Tooltips müssen Shortcut anzeigen.
* Menüeinträge (falls vorhanden) müssen Shortcut anzeigen.

## Motivation

Erlernbares Bedienkonzept.

---

# 6. Toolbar Icons statt Text

## Ziel

Reduktion visueller Unruhe.

## Anforderungen

* Text in Toolbar durch Icons ersetzen.
* Tooltips müssen Funktion + Shortcut anzeigen.
* Einheitliches Icon-Set (z. B. Qt Standard Icons).

## Motivation

Professioneller Look ohne Featureänderung.

---

# 7. Editor-Layout-Optimierung

## Ziel

Content-Fokus erhöhen.

## Anforderungen

### 7.1 Layout

* `content` groß und dominant (Hauptbereich).
* `sensors`, `actuators`, `image` kleiner und seitlich angeordnet.
* `printable` als Checkbox klar sichtbar.

### 7.2 Keine Logikänderung

* Nur UI-Anordnung.
* Keine Änderung an Domain oder Commands.

## Motivation

Bessere Lesbarkeit bei großen Textblöcken.

---

# Zusammenfassung der Priorisierung

Empfohlene Reihenfolge:

1. Schema Evolution (0)
2. Multi-Instanz (1)
3. DnD innerhalb Instanz (2)
4. Kontextmenü (4)
5. Shortkeys (5)
6. Icons + Layout (6–7)
7. Cross-Instance DnD (3)

Begründung:
Cross-Instance DnD ist technisch komplex und sollte erst nach Stabilisierung erfolgen.

---

# Scope-Grenze

Nicht enthalten:

* Asset-Embedding
* ID-basierte Synchronisation
* Git-Integration
* Realtime Collaboration
* Branching Undo-History
* Struktur-Metadaten im Flatten/Expand

---

Wenn du willst, gehen wir jetzt strategisch vor:

* Wählen wir **einen** Punkt (z. B. Multi-Instanz).
* Ich formuliere daraus ein präzises Addendum inkl. Akzeptanztests.
* Und wir bauen es inkrementell ein.

Du hast jetzt ein sauberes, kontrollierbares Erweiterungsmodell.
