## Intro
This is a helper skill to configure and manage the lossless-claw plugin for openclaw.

Lossless Context Management plugin for OpenClaw, based on the LCM paper. Replaces OpenClaw's built-in sliding-window compaction with a DAG-based summarization system that preserves every message while keeping active context within model token limits.

## Resources
- Repo: https://github.com/Martian-Engineering/lossless-claw
- README: https://github.com/Martian-Engineering/lossless-claw/blob/main/README.md
- docs sources: https://github.com/Martian-Engineering/lossless-claw/tree/main/docs

## Instructions
Scrape the README and the docs and compile a skill that helps the agent to understand the plugin, how to install, configure and use it. Use the skill-builder skill to create and validate the skill according to best practices.

Just copy all the files from docs into references and put the information from READ.me into SKILL.md, only skip the development and projects tructure and move the enviroment variables to the configuration.md

### SKILL.md
Explain what it is and give an overview of it usage and where to find the detailed information in the references.
Structure see ./skill-templates/helper-skill.md
