# VAULT_NAVIGATION.md

The vault navigation requires ripgrep. If it is not installed you must tell the user to install it.

## 1. Architectural Principles

The vault is designed as a queryable graph database implemented entirely through plain-text files. It utilizes four interdependent layers to provide database capabilities without a server:

* **Wiki Links (Graph Edges):** Human-curated connections that serve as semantic graph edges.
* **YAML Frontmatter (Node Properties):** Structured attributes that define every entity's dimensions (e.g., type, topics, status).
* **Ripgrep (Query Engine):** The high-speed engine used for structured property queries and multi-dimensional filtering.
* **Validation Agents (Data Integrity):** Asynchronous checks that maintain schema consistency over time.

## 2. Navigation Strategies

Agents should employ a multi-layered discovery approach to maintain orientation:

1. **Top-Down (Structural):** Start at the `index.md` or specific Maps of Content (MOCs) to identify thematic hubs and high-level clusters.
2. **Bottom-Up (Associative):** Follow curated wiki links within notes to explore semantic relationships and adjacent claims.
3. **Cross-Cutting (Query-Based):** Use `ripgrep` to filter by facets (e.g., "find all evergreen notes of type: tension").

## 3. Ripgrep Pattern Library

Use these named patterns for interacting with the file system:

### Pattern: **Structured Property Query**

Queries specific YAML fields; functionally equivalent to a SQL `WHERE` clause.

```bash
# Find notes of a specific type
rg '^type: tension' notes/

# Find notes with a specific status
rg '^status: evergreen' notes/

```

### Pattern: **Backlink Discovery**

Reveals the usage context and relationship graph of a specific note.

```bash
rg '\[\[Note Title\]\]' --glob '*.md'

```

### Pattern: **Faceted Dimension Filter**

Pipes independent YAML facets to achieve high-precision results.

```bash
rg '^type: pattern' notes/ | xargs rg -l '^methodology: Original'

```

### Pattern: **Topic Map Traversal**

Identifies all nodes belonging to a specific dimension in the topic map.

```bash
rg '^topics:.*\[\[methodology\]\]' notes/

```

### Pattern: **Integrity Scan**

Identifies notes missing mandatory metadata fields to prevent "query rot".

```bash
# Find notes missing a description field
rg -L '^description:' notes/*.md

```

### Pattern: **Breadth-First Description Scan**

Scans all descriptions to enable rapid filtering before loading full content.

```bash
rg '^description:' notes/

```

## 4. Search Modality Decision Matrix

Select the appropriate tool based on the task requirement:

| Task | Mode | Tool | Justification |
| --- | --- | --- | --- |
| File Path/Title Check | Keyword | `rg` | Instant and precise for exact matches. |
| YAML Field Query | Keyword | `rg` | Best for deterministic structural filtering. |
| Conceptual Exploration | Semantic | `vector` | Crosses vocabulary boundaries to find meaning. |
| Duplicate Detection | Semantic | `vector` | Catches same-idea-different-words overlaps. |
| High-Stakes Connection | Hybrid | `deep` | Uses LLM reranking for maximum relationship quality. |

## 5. Topics Links

### Topics Links in the Frontmatter (The Database Layer)

The frontmatter transforms a plain text file into a structured record. By placing topics: ["[[topic-name]]"] in the YAML header, the topic becomes a pre-computed, queryable dimension.

- Function: It enables faceted, multiplicative classification.
- Mechanism: This allows retrieval engines to filter notes through independent metadata axes. You can execute deterministic property queries (e.g., finding all notes intersecting a specific topic, a specific type, and a specific methodology) with high precision without reading the file body.

### Topics Links in the Footer (The Topology Layer)

The footer links integrate the isolated note into the vault's associative network. Placing [[topic-name]] in the markdown body acts as an explicit, intentional graph edge.

- Function: It enables backlink discovery and multi-hop semantic traversal.
- Mechanism: When navigating outward from a central Map of Content (MOC), these inline wiki links ensure the note is topologically connected to the topic's hub. This establishes the structural paths required for discovery when exact search terms fail.
