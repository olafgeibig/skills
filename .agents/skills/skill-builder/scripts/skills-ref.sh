#!/bin/bash
exec uvx --from git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref skills-ref "$@"
