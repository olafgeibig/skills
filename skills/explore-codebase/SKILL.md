---
name: explore-codebase
description: Explore and understand codebases. Use this when analyzing source code, manifests and other config for software engineering tools like kubernetes, helm, terraform. Usually the codebases are cloned git repositories in a directory `./repos/`
---

## When to use

- Use this skill when exploring a repository under `./repos/` in a security analysis project.
- Use `./REPOS.jsonl` to decide whether the repo is a software project (`is_software_project: true`).

## Required / companion skills

When the repo is a software project, load these skills first:

- `code-review-graph-usage` (how to call CRG MCP tools via `mcp-cli` correctly)
- `codebase-inspection` (optional: quick LOC/language breakdown via `pygount`)

## Repos

The `./repos/` directory containing the git repos to analyze is in .gitignore.

./REPOS.jsonl contains a list of the repositories to be analyzed. The jsonl file shall be well formatted that it is human readable. The format of a list entry:
```
{
  "repo_dir": "string. The exact directory name or path of the repository.",
  "description": "string. Purpose and contents of the repo.",
  "security": "string. Cybersecurity relevance reason.",
  "is_software_project": "boolean. True ONLY if the primary purpose of the repository is application or library source code. Must be false if the repository consists primarily of infrastructure-as-code, documentation, or CI/CD manifests.",
  "supported_source_languages": "array of strings. List the primary programming languages found. ONLY select from this exact list: [Python, TypeScript, JavaScript, Go, Rust, C++, Java, C#]. If 'is_software_project' is false or no languages from the list are present, output an empty array []."
}
```

## CRG MCP tool discovery (authoritative)

Do not hardcode MCP tool parameter schemas here (they change).

When you need the current list of Code Review Graph MCP tools and their parameters, run:

`mcp-cli info code-review-graph`

Core tools you will typically use in this skill:

- `get_minimal_context_tool`
- `get_architecture_overview`
- `list_graph_stats_tool`
- `list_communities_tool` / `get_community_tool`
- `list_flows_tool` / `get_flow_tool`
- `query_graph_tool`

## Explore Codebase

- Use the code-review-graph tools to explore and understand the codebase (software repos). For non-software repos, use `search_files`.

### Evidence rule: README is not proof of implementation

When the task is to verify whether a technology is *actually used* (e.g., RabbitMQ vs Kafka), do **not** treat README or other narrative docs as evidence.

Preferred evidence sources:
- Call graph evidence (CRG): `callers_of` / `children_of` from runtime entrypoints (controllers, schedulers, main).
- Runtime configuration/manifests under `repos/*deploy*/`.
- Code-level invocations (imports + method calls), corroborated by call paths.

### Pattern: "dual publish" indicates partial migration

When you find code that publishes the same payload to two brokers (e.g., Rabbit + Kafka) in one method, record it explicitly as a migration/strangler signal, and then trace at least one non-test call stack into that method using CRG.

(Do not claim "legacy" unless you can show the code is unreachable from non-test call stacks and absent from deployed configs.)

### Message-bus usage verification (RabbitMQ / AMQP / Kafka)

When asked whether a technology (e.g., RabbitMQ/AMQP/CloudAMQP) is *really still in use* vs just legacy:

1) **Reject README-only evidence**
   - Treat README mentions as potentially stale.
   - Only accept: runtime code paths + runtime configuration/manifests.

2) **Two-layer evidence approach**
   - Layer A (presence): `rg --no-ignore` or `search_files` across `repos/` for client libraries + URLs + config keys.
   - Layer B (actual use): use CRG call graph to prove the code is on a production call stack.

3) **CRG call-stack proof pattern (preferred)**
   - Build/update graph for the specific repo.
   - Find a concrete send/consume function (e.g., `RabbitTemplate.convertAndSend`, a `*Sender.sendMessage`, a `RabbitStreamTemplate` publisher, etc.).
   - Use `query_graph_tool` with:
     - `pattern="callers_of"` on the publisher/consumer method
     - then chain `callers_of` upward until you hit a likely entrypoint:
       - REST controller method, scheduler, message listener, CLI entrypoint
   - Distinguish results:
     - If callers are only `Test` nodes → likely not used in production.
     - If at least one caller is a non-test `Function` under main code → evidence of runtime use.

4) **Config vs code mismatch handling**
   - If code publishes to both Rabbit + Kafka, document as a deliberate migration/strangler pattern, not “Rabbit unused”.
   - If config exists but CRG shows no production call stack, label as “candidate legacy/debt” (and list the exact code nodes/config keys).

5) **CloudAMQP nuance**
   - Infra references (e.g., external secret names/ARNs containing `cloudamqp`) prove credential provisioning exists, but do not alone prove runtime traffic.
   - Require code-level usage + binding to those credentials (env vars/config keys) to claim CloudAMQP is active.


### Pitfall: absolute vs relative paths when writing outputs

When creating project artifacts (reports/changelogs) under the repository:

- Prefer workspace-relative paths (e.g. `repo-util/<file>.md`).
- Only use absolute paths when the user explicitly asked for an absolute path.
- Always verify with a directory listing (`ls -la <dir>`) that the file exists where expected BEFORE claiming it was written.

Failure mode (seen in practice): writing to `repo-util/...` while the tool resolves paths differently than expected, leading to a file being created outside the workspace and the user not finding it.

Verification pattern:
- After `write_file(path="repo-util/<name>.md", ...)`, run `ls -la repo-util/` and confirm the filename appears.
- If the user wants an absolute path, write to that absolute path AND still verify with `ls -la <absolute_dir>/`.

This avoids "I don't see the file" loops and makes the change artifacts defensible.
+

### Pitfalls

0) Mixed Bosch deployment/code architecture analysis: start from deployment manifests, then prove runtime behavior in code

When the user asks for an architecture analysis of a mixed deployed system (especially MRT/Kubernetes + multiple repos), do not jump straight into application source code or CRG.

Use this sequence:
- First inspect the deployment/IaC repo to establish the live component model:
  - namespaces
  - HelmRelease/Kustomization structure
  - ingress / VirtualService hosts and gateways
  - image repositories/tags
  - SealedSecrets / ConfigMaps / storage references
- Then inspect application repos to prove what each deployed service actually does.
- Keep claims separated into:
  - deployment-proven facts
  - code-proven facts
  - stakeholder-stated but still unverified facts

Important Bosch-specific pattern observed in practice:
- A deployment repo may keep non-software repos in project scope even when they are excluded from CRG.
- Shared runtime context matters: if multiple features piggyback on the same namespace / hostname / API service, record that explicitly as architecture evidence and scope risk.
- Separate namespaces/gateways for auxiliary apps (for example a validation SPA) are important trust-boundary evidence and should be called out explicitly.
- When a user suspects a feature-specific flow is hidden inside a broader shared frontend, do not over-attribute the whole frontend to that feature. Separate these cases explicitly:
  - feature-specific UI/code that is directly evidenced
  - shared/general product functionality that merely coexists in the same app
  - missing backend evidence that still prevents end-to-end attribution
- For onboarding/import analysis, do not infer a manual file-upload workflow from words like "onboarding" or from VIN fields alone. Prove it by finding concrete browser-side evidence such as `<input type="file">`, `FileReader`, CSV/XLSX parsing, upload handlers, or a dedicated import endpoint. If the frontend only triggers generic backend calls like `POST /vehicles`, describe that as backend-triggered onboarding, not user-side list upload.
- Treat backend route names such as `/vehicles-onboarding`, `/mass-onboarding`, `/registered-vehicles`, or `/tesla/specs` as distinct ingestion mechanisms until proven otherwise. Do not collapse them into one story. For each candidate path, identify:
  - required request fields
  - which collections are written
  - whether a fixed `fleetId` is injected server-side
  - whether the path creates base vehicle records, enriches existing ones, or both
- If a private backend service is visible only indirectly, reconstruct the public-to-private chain explicitly:
  - user-facing frontend/API endpoints
  - orchestration/backend endpoint names
  - private service routes
  - storage/download handoff such as presigned S3 URLs
  This keeps "download happens in the UI" separate from "file is actually served by object storage via backend-generated URL".
- When a newly added repo is expected to be rich but CRG indexes only one or very few files, do not treat the graph as authoritative yet. Record the partial-index symptom, use direct file search/reads first, and only rely on CRG again after a fuller rebuild/verification.
- For shared frontends/API landscapes, distinguish carefully between three evidence levels when the user asks whether a feature-specific interface "really exists":
  - code capability exists (e.g. shared webapp contains certificate download UI and calls)
  - backend/API capability exists (e.g. endpoints and orchestration routes exist)
  - operational/project interface status is confirmed by stakeholders
  Do not collapse these into one claim. If code shows a feature in a shared UI but stakeholder input says only API + a dedicated app are intended interfaces, report the code capability as real while explicitly marking operational relevance/scope as unconfirmed.
- When the user decides to trust stakeholder clarification for scope/interface selection, update the architecture output to the narrowed relevant component set instead of preserving superseded shared-UI speculation. In practice for DFT CSL overview notes: remove de-scoped shared frontend discussion from the main architecture narrative and keep the overview centered on the currently accepted interfaces/components.
- For Tesla or other external-data ingestion analysis, trace the full normalization chain rather than stopping at the outbound API call:

  - separate identities/clients per tenant
  - tenant-scoped authorization checks on retrieval routes
  - storage isolation (bucket/prefix/service split)
  - object lookup keys that include tenant context rather than only business identifiers
  If the code only shows fleet- or company-based branching inside shared collections/services, describe that as logical tenant separation, not hard technical isolation.
- For Tesla or other external-data ingestion analysis, trace the full normalization chain rather than stopping at the outbound API call:
  - find the external client/token flow
  - find the route that accepts the input identifiers (for example VIN lists)
  - prove how returned fields are mapped into local collections/fields
  - then prove which downstream API endpoints and certificate-generation paths read those same local fields
  This is the defensible way to answer "how do identifiers reach the provider" and "how do provider data become certificate inputs".
- When a system mixes tenant/fleet metadata with ingestion routes, distinguish carefully between:
  - evidence that a fleet/company object exists and names a logical tenant
  - evidence that a given ingestion path writes records with a fixed fleet ID
  - evidence that a separate manual onboarding step is required before enrichment
  If the enrichment route itself upserts vehicle records with the tenant/fleet marker, say that directly and do not invent an earlier mandatory onboarding step.
For MRT-style deployment evidence, prefer concrete fields such as:
- `metadata.namespace`
- `virtualService.host` / `virtualService.gateway`
- `image.repository`
- `service.ports`
- `configMaps.data`
- `secrets` / `SealedSecret`
- `source.toolkit.fluxcd.io` / `helm.toolkit.fluxcd.io` / `kustomize.toolkit.fluxcd.io` resource kinds

This avoids drifting back into stale architecture narratives and produces a defensible manifest-first system view before tracing runtime code paths.

0) Repo inventory vs active analysis set must be kept separate when excluding deployment/IaC repos from CRG

When a project mixes software repos and deployment/IaC repos, do not conflate these two decisions:
- whether a repo belongs in the project inventory (`repos.json`, repo manifest, etc.)
- whether a repo should be actively indexed/analyzed with Code Review Graph

Rule:
- Keep deployment/IaC repos in the project inventory when they are part of the delivered system or deployment model.
- Exclude them from the active CRG workset when the goal is source-code architecture/call-graph analysis and the repo is not a software project.
- Do not remove a repo from manifests/inventory merely because it should not be rebuilt in CRG.

Practical pattern:
- `repos.json` / repo manifest answer: what belongs to the project scope?
- CRG selection answers: which repos are worth source-code graph indexing right now?

This matters in mixed Bosch CSL projects where deployment repos remain security-relevant evidence even if they are not useful CRG targets.

0) README-as-evidence is not acceptable for implementation claims

When the user explicitly says README findings are not approved/outdated, treat README as non-evidence.

Rule for messaging/tech-debt verification tasks (RabbitMQ/Kafka/etc.):
- Prefer code-level evidence (imports, wiring, bean creation, call sites) and deployment manifests.
- Use Code Review Graph call stacks (e.g., `callers_of` from publisher/consumer to controllers/schedulers) to show runtime reachability.
- Only mention README claims as “soft context” if you also provide hard evidence.

0) Skill name resolution gotcha

Skill names are addressed by their slug (e.g. `explore-codebase`). UI listings may show a title-cased label ("Explore Codebase").
If loading by title fails, use the slug form.

1) Avoid read_file dedupe blockers when a file changes mid-session

In some Hermes environments, repeated `read_file` calls on the same file region can be blocked if the agent previously read it and the system believes it is unchanged.
If the user says they updated a file but `read_file` is blocked:

- Verify the file changed via `stat` (mtime/size).
- Read via shell to bypass the dedupe guard (e.g., `sed -n '1,200p <file>'`).
- Then apply edits with the file tools (`patch` / `write_file`) as usual.

Why: this prevents getting stuck on stale content when reviewing/patching project guidance (e.g., AGENTS.md) during active edits.

Extra pitfall (from recent sessions): if the user reorganized directories, do a quick live directory listing (e.g., `ls -la` + `find . -maxdepth 2 -type d`) before suggesting doc changes. Don’t rely on earlier session memory for paths.



Skill names are sometimes listed with title case/spaces ("Explore Codebase") but addressed via a slug (e.g. `explore-codebase`).
If loading by title fails, use the slug form.

Also note: project docs may refer to a display name, but the agent should always use the canonical slug when calling `skill_view()`/loading skills.

1) CRG "update was too fast" is often normal — verify with `last_updated`

After `git pull`, CRG may update only a handful of files (often just `CHANGELOG.md` / `gradle.properties`). A quick run is not suspicious by itself.

Verification pattern (per repo):
- `mcp-cli call code-review-graph list_graph_stats_tool '{"repo_root":"repos/<repo>"}'`
  - Check `last_updated`.
- If `last_updated` is older than the last `git pull`, run:
  - `mcp-cli call code-review-graph build_or_update_graph_tool '{"repo_root":"repos/<repo>","full_rebuild":false}'`
  - Then re-check `last_updated`.

Multi-repo update/verify workflow: see `references/crg-multirepo-update-and-verify.md`.

2) Multi-repo "change set" needs a stable baseline — don’t use `git log --since` for pulls

If you forgot to record pre-pull SHAs, you can reconstruct a robust baseline per repo from local reflog:
- baseline = commit at `reflog` entry that contains `clone:`
- diff = `git diff --name-status <baseline>..HEAD`

Why: `git log --since=<clone_date>` can be misleading (commit author/committer dates vs fetch time).
Use reflog-based SHAs for any security-impact/change-surface analysis.

### Pitfalls

0) Change-set reconstruction after `git pull`: prefer reflog-based diffs, not `--since`

When you need to analyze “what changed since I last had the repos cloned” (e.g., after running a batch `git pull`), do NOT rely on:
- `git log --since=<clone_date>`

It can miss changes you actually pulled (e.g., commits created earlier than the clone timestamp but fetched/pulled later; branch date quirks; misleading timestamps).

Preferred evidence-led approaches:
- For a clean “current vs original clone” baseline (if available):
  - baseline SHA = the `git reflog` entry containing `clone:`
  - diff = `git diff --name-status <baseline>..HEAD` (+ `--shortstat`)
- For “what did the last pull change”:
  - diff = `git diff HEAD@{1}..HEAD` (when reflog has a pull entry)

Always record:
- which baseline you used (clone vs previous HEAD)
- the exact SHAs and repo paths

1) `search_files` vs `rg --no-ignore` under `./repos/`

`search_files` behavior under `repos/` can vary by Hermes version/config because `repos/` is in .gitignore.

Rule:
- You MAY start with `search_files` for convenience.
- But never conclude “pattern not found in repos/” from `search_files` alone.
- If the claim matters and results are empty/suspicious, cross-check with:
  - `rg --no-ignore -n "<pattern>" repos/<repo_dir>/`

This avoids false “not found” conclusions when ignore-handling changes.

2) `REPOS.jsonl` format gotcha (DFT workspace)

In this workspace, `REPOS.jsonl` is **not strict JSONL** (one JSON object per line). It is a concatenation of pretty-printed JSON objects spanning multiple lines.

Rule:
- Do NOT parse it with `json.loads(line)` per line.
- If you need to parse it programmatically, use a streaming JSON decoder to read consecutive objects.
- Otherwise, treat it as a human navigation file and use `read_file` / `rg '"repo_dir"'` to locate entries.

4) Git baseline selection pitfall (IMPORTANT)

When you need a change set across many repos, separate two different use cases:

- historical reconstruction when no explicit snapshot exists yet
- ongoing snapshot-to-snapshot comparison after a manifest-based workflow was introduced

Do **not** rely on `git log --since=<clone_date>` for either case.

Reason: commits can have timestamps older than your clone date yet only get fetched and fast-forwarded later.

Preferred approaches:
- Legacy/historical reconstruction:
  - baseline commit = `git reflog` entry containing `clone:` (the local post-clone HEAD)
  - compare with `git diff <baseline>..HEAD` (name-status + shortstat)
- Current/canonical workflow:
  - compare explicit repo snapshots recorded in manifests
  - baseline = older `repos-manifest.yaml` snapshot
  - target = current `repos-manifest.yaml` snapshot
  - per repo, diff `baseline_ref..target_ref`

Important distinction:
- reflog/clone baselines are a fallback or migration aid
- once a project has an explicit repos manifest, manifest-to-manifest comparison is the preferred method because it is reproducible and not dependent on local reflog retention

If a repo manifest is used to record checked-out refs, capture the actual checkout state, not just the policy-derived "latest" ref. In practice this means:
- always record `commit`
- optionally record `tag` when HEAD is exactly at a tag
- optionally record `branch` when attached to a branch
- do not treat "latest tag currently existing in the repo" as equivalent to "the tag actually checked out"

For helper-script design in this class of workflow:
- a `*_update_latest*` script may implement policy such as latest tag / main / remote default branch
- a separate checkout-from-manifest script should enforce an explicit snapshot
- capture-manifest logic should describe the real current checkout state so it also works after explicit snapshot checkout, not only after latest-policy update

3) Public interface inventory: include auxiliary UIs and ingress routing evidence

When the user asks for "interfaces" / "public endpoints", include not only the main Portal/UI and REST APIs but also auxiliary user-facing components deployed alongside them (e.g., Swagger UI / api-viewer).

Also capture the routing layer as an interface element when it exists (e.g., Istio Gateway/VirtualService), because it is the concrete boundary that maps public hostnames/paths to services.

Validate with:
- HelmReleases under `repos/*deploy*/stages/*/services/*/helm-release.yaml` (hosts + gateways)
- Istio VirtualServices / Gateways under `repos/*deploy*/stages/*/services/**/vs*.yaml` or `repos/*deploy*/stages/*/services/commons/**` (path routing like `/docs`, `/api-docs`, `/apis/*`)
- Component-specific config that shows routing/proxying behavior (e.g., api-viewer spec proxy rules)

4) External interface claims need evidence

When inferring external interfaces from config:
- Queue/topic names (e.g., containing a partner name) are **hints**, not proof of the external publisher.
- Document as “inbound interface consumed by DFT” unless you have publisher-side evidence.

### Steps

1. Identify repo type using `./REPOS.jsonl`.

2. **Hard-evidence workflow discovery (security testing / CI controls)**

When the task is to validate what security testing is *actually implemented* (SAST/DAST/scanning), do **not** rely on doc claims.

Do this first:

- Enumerate workflow files:
  - `find repos -path '*/.github/workflows/*' -type f \( -name '*.yml' -o -name '*.yaml' \)`
- Search for key markers (cross-check with `rg --no-ignore` if needed):
  - SAST: `sonarqube|sonar\.projectKey|sonarsource/sonarqube-scan-action|org\.sonarqube`
  - DAST/ZAP: `OWASP ZAP|zaproxy|zap-|owasp-dast|DAST`
  - Container/image scanning: `trivy|grype|syft|anchore|snyk|dockle|container scan|docker scan`
  - SBOM/OSS scanning: `sbom|cyclonedx|fosslens|dependency-track`

Then, for any workflow you cite, **open the file** and extract the hard signals:
- trigger (push/PR/schedule)
- target environment
- notification mechanism (e.g., Teams webhook)
- enforcement (quality gate wait, blocking thresholds, failing the workflow)

Pitfall:
- `search_files` under `./repos/` may yield false negatives due to ignore handling; never conclude “not present” without `rg --no-ignore`.

3. If `is_software_project: true`: follow the “Software repo (CRG)” flow below.
4. Else: follow the “Non-software repo (file tools)” flow below.
### Steps

1. Identify repo type using `./REPOS.jsonl`.
   - Note: in this workspace, `REPOS.jsonl` is **not strict JSONL**. It is a concatenation of pretty-printed JSON objects spanning multiple lines. Treat it as human navigation unless you implement a streaming decoder (see references).
   - Quick validation (optional): `python3 -c 'import json; [json.loads(l) for l in open("REPOS.jsonl") if l.strip()] ; print("ok")'`
2. If `is_software_project: true`: follow the “Software repo (CRG)” flow below.
3. Else: follow the “Non-software repo (file tools)” flow below.

4. If the task is **"what security testing/scanning exists"** (CI/CD evidence gathering):
   - Start with `search_files()` for key tool markers across `repos/`.
   - If results look empty/suspicious (common when `repos/` is ignored), cross-check with ripgrep:
     - `rg --no-ignore -n "<pattern>" repos/`
   - Then open the exact workflow/config files with `read_file` and capture evidence as:
     - repo-relative file path
     - what it does (trigger, tool, gating, notifications)

   Recommended marker patterns (adjust as needed):
   - SAST/quality: `sonarqube|sonar\.projectKey|sonarsource/sonarqube-|org\.sonarqube`
   - DAST/runtime: `OWASP ZAP|zaproxy|zap-x\.sh|owasp-.*dast|frontend-authenticated-plan\.yaml`
   - Vulnerability scanning: `trivy|aquasecurity/trivy-action|grype|syft|anchore|snyk`
   - IaC/K8s posture: `trivy config|pluto detect-files|kube-score|kube-linter`
   - OSS/SCA: `fosslens|sbom|cyclonedx|dependency-track`

   Pitfalls:
   - Don’t rely on `CHANGELOG.md` mentions as evidence of a control existing; require a workflow/config/script reference.
   - When you claim a control exists, cite the exact file path(s) under `repos/`.



0. Verify CRG tool availability and schema once per session:
   - `mcp-cli info code-review-graph`
1. Build/update the graph:
   - `mcp-cli call code-review-graph build_or_update_graph_tool '{"repo_root":"...","full_rebuild":false}'`
2. Verify parsing worked (don’t assume):
   - `mcp-cli call code-review-graph list_graph_stats_tool '{"repo_root":"..."}'`
   - Confirm non-zero nodes/edges and expected languages (e.g., java).
3. Proceed with exploration (minimal context → architecture → query_graph).

#### Non-software repo (file tools)

1. Use file listing and targeted reads to identify high-signal artifacts (README, CI, deploy manifests, scripts).
2. Use search_files with fall back to ripgrep
3. Summarize purpose, structure, and security-relevant artifacts with concrete file paths.

### References
- `references/rabbitmq-kafka-usage-verification.md` — evidence-led workflow to determine whether RabbitMQ/AMQP is actually used vs legacy (uses CRG call stacks; README is not evidence when disallowed).

- `references/security-testing-evidence-from-repos.md` — checklist/template to collect hard evidence of implemented SAST/DAST/scanning from repo artifacts (workflows/actions/config).
- `references/repos-search-crosscheck.md` — why `search_files` may yield false negatives under `./repos/` and when to cross-check with `rg --no-ignore`.
- `references/repos-jsonl-format-gotcha.md` — DFT workspace nuance: `REPOS.jsonl` is not strict JSONL; parsing guidance.
- `references/reflog-based-change-sets.md` — reconstruct multi-repo change sets after batch `git pull` (use reflog-based baselines; avoid `--since` traps).
- `references/dft-interfaces-and-dataflows-doc-workflow.md` — DFT-specific doc workflow notes (interfaces, dataflows, SFTP/SQS, api-viewer, ingress evidence).
- `references/dft-interface-docs-consistency-checklist.md` — checklist to keep interface docs consistent with architecture/diagrams.
- `references/reviewing-and-patching-agents-md.md` — checklist/workflow for keeping `AGENTS.md` consistent with the actual repo layout and toolchain.
- `references/reviewing-agents-md-during-layout-changes.md` — session notes: directory drift, `read_file` dedupe bypass, and skill-name gotchas.
- `references/dft-repo-diff-to-doc-changelog.md` — how to turn a multi-repo diff report into an evidence-led, doc-impact changelog (agent-facing).
- `references/dft-repo-diff-to-doc-changelog-2026-06-session.md` — session note: practical checklist + verification pattern to avoid misplaced outputs.

(Updated 2026-06: includes a verification step to ensure the file is written under the correct workspace `repo-util/` path before reporting success.)

- Start broad (stats, architecture) then narrow down to specific areas.
- Use `children_of` on a file to see all its functions and classes.
- Use `find_large_functions` to identify complex code.

## Token Efficiency Rules
- For CRG: ALWAYS start with `get_minimal_context(task="<your task>")` before any other graph tool.
- Only pass `detail_level="minimal"` to tools that accept it (e.g. `list_communities`, `list_flows`, `query_graph`, `get_impact_radius`). Do NOT pass `detail_level` to `get_minimal_context`.
- Target: complete any review/debug/refactor task in ≤5 tool calls and ≤800 total output tokens.
