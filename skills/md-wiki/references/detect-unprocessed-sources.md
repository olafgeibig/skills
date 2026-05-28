# Detecting Unprocessed Raw Sources

When the user says "process the new articles in raw/articles/" or you want to find sources that haven't been ingested yet:

1. List all files in `wiki/<target>/raw/articles/` (via `terminal` or by reading the directory)
2. For each file, search entity and concept pages for a `sources:` reference to that filename:
   `mcp_turbovault_search(query="raw/articles/<filename>")`
3. If no entity/concept page references it → the source is **unprocessed**
4. Report the list to the user and ask which to ingest

The `raw/articles/` directory acts as the signal — any file there not yet referenced by an entity or concept page is pending processing.
