## Intro
This is a helper skill to configure and manage the memory-lancedb-pro plugin for openclaw.

Enhanced LanceDB memory plugin for OpenClaw — Hybrid Retrieval (Vector + BM25), Cross-Encoder Rerank, Multi-Scope Isolation, Management CLI

## Resources
- Repo: https://github.com/CortexReach/memory-lancedb-pro
- README: https://github.com/CortexReach/memory-lancedb-pro/blob/master/README.md
- docs sources: https://github.com/CortexReach/memory-lancedb-pro/tree/master/docs

## Instructions
Scrape the README and the docs and compile a skill that helps the agent to understand the plugin, how to install, configure and use it. Use the skill-builder skill to create and validate the skill according to best practices.

Just copy all the files from docs into references and put the information from README.md into SKILL.md, but skip the comparison and project structure and move these topics of the README into its own reference file and link it in the SKILL.md:
- Section "Configuration" -> configuration.md
- Section "Installation" -> installation.md
- Section "Advanced Topics" -> advanced.md
- Convert the Section "Documentation" to links to the downloaded docs in reference dir

### SKILL.md
Explain what it is and give an overview of it usage and where to find the detailed information in the references.
Structure see ./skill-templates/helper-skill.md
Use the product version in the SKILL.md version meta property in the frontmatter
