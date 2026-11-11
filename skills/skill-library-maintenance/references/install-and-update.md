# Install & Update

Bring an installation of the Stage & Integrate sync into being — a new machine or a new
profile on an existing one — and move an existing installation between versions. Mechanics, run
books and diagnosis live in `shared-repo-sync.md`; the renderable prompts and blocks in
`../assets/`. Roles do not come from this file: the installation's own identity (`SOUL.md` or its
`hermes-profile-*` skill) says which role it plays.

**Deployment is separate from the repository.** Editing a template, asset or script here installs
nothing: rendering the templates, creating cron jobs, running the installer and writing the first
vault report are distinct operator-approved deployment actions. A repository change must never be
reported as an active job, hook or report.

## Roles

**What lands on a transport branch is always pre-integrated: the staging sweep commits locally,
the pre-integration run owns the push, the maintainer only ever sees cleaned content.**

Exactly two, and they differ in one job only:

| Role | Who | Writes `main`? | Jobs |
|---|---|---|---|
| **Maintainer** | exactly one machine in the whole setup | yes — the only writer | staging sweep · pre-integration · integration (monitor-gated) |
| **Contributor** | every other installation | never | staging sweep · pre-integration |

Both run the hourly staging sweep (bundles pending work into one transport commit on
`machine/<host>`, locally — no push) and the daily pre-integration (the instance
cleans its own pending net: instance-shaped lessons out of canonical skills, valuable ones into
the profile's adaptation; then it pushes). Only the Maintainer additionally runs the
monitor-gated integration (a 30 min tick — the agent wakes only when a transport branch has
new content) — it
consumes the transport branches and lands them on `main`, one commit per consumed branch
(*Maintainer run book* in `shared-repo-sync.md`).

## Installation (new)

### Values

Five, and the agent already knows where to find them:

- `{machine}` — the logical name from the machine table in `hermes-projects` (verify with `hostname`)
- `{skills_repo}` — the shared checkout's entry in `hermes config get skills.external_dirs`
- `{hermes_home}` — `$HERMES_HOME`
- `{store}` — `{hermes_home}/skill-repo-sync` (the maintainer store, version-independent; explicit `--store` target)
- `{maintainer_repo}` — the maintainer clone recorded as `maintainer_repo` in `{store}/maintainer.json` (explicit `--repo` target; the helper refuses any other checkout)

### Templates to render

Replace the `{var}` placeholders (each template's header comment lists its own variables — that
list is the template contract):

| Template | Renders to |
|---|---|
| `../assets/stage-sweep-script.sh.example` | `{hermes_home}/scripts/skill-repo-sync-stage.sh` (`chmod 755`) |
| `../assets/maintain-monitor-script.sh.example` | `{hermes_home}/scripts/skill-repo-maintain-monitor.sh` (`chmod 755`) |
| `../assets/pre-integration-cron-prompt.md.example` | the pre-integration job prompt |
| `../assets/maintainer-cron-prompt.md.example` | the integration job prompt (Maintainer only) |
| `../assets/skill-review-cron-prompt.md.example` | the proposed periodic whole-skill review prompt (one skill per run; not created by this checklist) |
| `../assets/soul-instance-block.md.example` | the identity block in `{hermes_home}/SOUL.md` (or the profile skill) |

### Components and jobs

| Piece | What | Roles |
|---|---|---|
| `on_session_start` hook | `--sync-from-main` via the wrapper | both |
| Wrapper | `{hermes_home}/bin/skill-repo-sync` — generated; execs the installed engine pair; the stable path hook consent binds to | both |
| Installed engine pair | `{hermes_home}/bin/skill-repo-sync.py` + `{hermes_home}/bin/skill_repo_workflow.py` (+ the report template) — copied together by the installer; identical versions or the install is refused | both |
| State | `{hermes_home}/skill-repo-sync.json` | both |
| Shim | `{hermes_home}/scripts/skill-repo-sync-stage.sh` — generated (see table above) | both |
| Monitor shim | `{hermes_home}/scripts/skill-repo-maintain-monitor.sh` — generated (see table above); prints the stable pending report (`--pending --store {store} --repo {maintainer_repo}`) for the maintainer job's monitor gate | Maintainer only |
| Staging sweep | hourly `:07` — bundles locally (no push); `no_agent`, shim, deliver telegram | both |
| Pre-integration | `30 3 * * *` — cleans and pushes; agent, skills `skill-governance` + `skill-library-maintenance` | both (per profile on a multi-profile machine) |
| Integration | monitor-gated (30 min tick; the agent wakes only when the pending report changes — no idle LLM runs); a fixed nightly slot is not required. Agent, skill `skill-library-maintenance` | Maintainer only |

Proposed but **not created by this checklist**: a weekly periodic whole-skill review (`0 4 * * 0`,
configurable) that reads one skill per run and advances the cursor in
`{store}/skill-review-cursor.json`. Render `../assets/skill-review-cron-prompt.md.example` only when
the operator approves that separate job.

### Reports destination and feedback

Reports go to the single plain directory in `report.path`; it is not hardcoded in the repository.
No vault handle, hub note or vault write path is involved — the agent writes the rendered bytes as a
regular file and reads them back:

1. Create nothing up front: the directory exists or the first write creates it.
2. The rendered note carries `type: zettel`, a short description and `skill-sync` plus, when the
   path contains `/projects/<name>/`, a `project/<name>` tag; do not add a second metadata copy.
3. The directory may sit inside a vault (`…/projects/hermes-agent/skill-sync-reports`); that only
   means Obsidian indexes the files, nothing depends on it.
4. The review note is immutable; the result note carries the outcome. To give feedback on an older
   report, name it in chat: the agent reads the report **and** the current skill, asks only if the
   correction is ambiguous, records its interpretation in a new feedback note or a result-linked
   correction report, and creates a normal corrective candidate. Never a blind `git revert` of the
   older merge; later work would be discarded.
5. No approve CLI and no human review queue exist. Technical failures block integration; ordinary
   semantic decisions are recorded in the report.

### Steps

1. **Render the templates** (values above) and place them at their targets.
2. **Create the jobs** (names, schedule and `--provider`/`--model`/`--pin` per local decision; the
   prompts are the rendered files):

   ```bash
   hermes cron create '7 * * * *' --no-agent --script skill-repo-sync-stage.sh \
     --name "skill-repo staging sweep (hourly)" --deliver telegram --workdir {skills_repo}
   # pre-integration: schedule at the end of the machine's typical usage window
   # (a missed run waits for the next schedule; there is no implicit resume catch-up)
   hermes cron create '30 3 * * *' "$(cat rendered-pre-integration-prompt.txt)" \
     --name "skill-repo pre-integration (instance review)" \
     --skill skill-governance --skill skill-library-maintenance \
     --provider <P> --model <M> --pin --deliver telegram --workdir {skills_repo}
   # Maintainer only — monitor-gated: the shim's byte-stable --pending report wakes the agent
   # only on change. --monitor-script takes the rendered shim's NAME under {hermes_home}/scripts/.
   hermes cron create '30m' "$(cat rendered-maintainer-prompt.txt)" \
     --name "skill-repo maintainer (monitor-gated)" \
     --skill skill-library-maintenance \
     --monitor-script skill-repo-maintain-monitor.sh \
     --provider <P> --model <M> --pin --deliver telegram --failure-deliver telegram \
     --workdir {skills_repo}
   ```

   The model pin is mandatory for agent jobs: an unpinned job resolves the config route at fire
   time and fails closed when `model.*` changes underneath it (*Crons* in `shared-repo-sync.md`).
3. **Installer.**
   `python3 {skills_repo}/skills/skill-library-maintenance/scripts/install-skill-repo-sync.py --bootstrap-current-ledger --apply-config --machine <name>`
   — `--bootstrap-current-ledger` is mandatory on a fresh install: it places the cursor at the
   current ledger end so historical entries are not transported. Without it the installer exits
   `12` and writes nothing (no wrapper, state, config or file mode). On an existing install omit
   the flag — the saved cursor is preserved, and passing the flag is itself refused (`12`).
   `--apply-config` reads `hooks.on_session_start` with `hermes config get … --json` and appends
   the wrapper's entry, leaving every other hook entry as it was; a hook that already runs the
   wrapper is left alone (no duplicate). It never writes `hooks.on_skill_lifecycle` — an old v1
   maintainer hook is retired deliberately (see *From 1.x* step 2), never blanket-cleared — and it
   never enables global auto-accept. An unreadable or non-list hook answer is a refusal, not a
   rewrite. Approve the resulting `(event, command)` pair through the normal consent flow.
   The installer copies the engine **and** its shared core (plus the report template) into
   `{hermes_home}/bin` before writing the wrapper; the pair must exist and report the same
   version, otherwise the install is refused before any wrapper, state or config write. The
   installer stages all new files and snapshots all previous targets before the first
   replacement. If any replacement raises (including interruption), it restores the previous
   engine, core and template byte-for-byte with their modes; a fresh-install rollback removes
   the new targets. If restoration itself fails, stop and use the retained recovery files named
   in the diagnostic. Multi-file replacement is not crash-atomic: the engine refuses a mixed
   pair, including in `--selfcheck` (exit 12). The wrapper path itself stays constant — hook
   consent binds to it. Installer `--version` prints its release without installation context
   or writes.
4. **Record the identity** — the rendered `SOUL.md` block (or a line in the profile's
   `hermes-profile-*` skill), so a fresh session knows its role and machine without asking.

### Verification

- `{hermes_home}/bin/skill-repo-sync --selfcheck --verbose` (the wrapper) or
  `python3 {hermes_home}/bin/skill-repo-sync.py --selfcheck --verbose` (the installed engine) —
  installed state, engine/core/installer versions (drift is a finding, see the deployment audit
  in `shared-repo-sync.md`), branch policy, maintainer config/report-root presence and lock state.
  Hook health is reported separately: `--selfcheck` deliberately makes no hook-health claim.
- `hermes hooks list && hermes hooks doctor` — the `(event, command)` pair allowlisted and healthy;
  configured is not activated. The list still carries every hook entry it had before installation:
  the installer appends its own entry, never replaces the list and never clears
  `on_skill_lifecycle`.
- `hermes cron list` — the expected jobs (two, plus integration on the Maintainer) with the
  intended schedules, skills and pins.
- Wrapper `--stage --dry-run --verbose` — what the next sweep would bundle into the transport
  commit; no state change.

## Update

When the operator tells you to install or upgrade this installation's sync: follow this
document. You already know your own values — `{machine}` and `{profile}` come from your identity,
the rest from the value recipe above. Fresh installation → *Installation (new)*. A version
transition below → its checklist first, then the *Installation* steps for anything it adds.
Report with the *Verification* checklist: every command and its result line, the rendered job
prompts quoted, the created job names — and anything that did not fit the documented model.
Never write `main`, never force, never discard a dirty worktree.

### From 1.x (the rescue state) to 2.1

The one-time rescue left contributors in a minimal state: a rescue commit pushed to
`machine/<host>`, v1 hooks emptied, the v1 safety/audit jobs paused, no engine install. Bring such
an installation to 2.1 with this checklist:

1. **Checkout current.** `git -C {skills_repo} fetch origin --prune`, then `git checkout
   machine/<name>` (the integrated tip). If the local branch still carries consumed commits,
   fast-forward it to `origin/machine/<name>` (`git merge --ff-only`); if it cannot fast-forward,
   keep the old tip with a `backup/` ref and inspect — never reset or discard work silently.
2. **Retire the v1 jobs and the v1 hook.** `hermes cron list`, then `hermes cron remove <id>` for
   the paused "skill-repo-sync safety" and "skill-library monthly audit" jobs — they invoke
   retired v1 modes (`--safety`, `--audit`) and only produce noise. If `hermes hooks list` still
   shows the retired `on_skill_lifecycle` maintainer hook (v1 fired it per skill write), empty it
   (`hermes config set hooks.on_skill_lifecycle '[]'`) and revoke its stale consent pair
   (`hermes hooks revoke <wrapper path>`, then let the installer's pair re-consent in the next
   step) — only `on_session_start` survives, and keeping the dead pair approved is just confusion
   fuel.
3. **Installation steps** above (render, jobs, installer with `--apply-config --machine <name>`,
   identity record).
4. **Verify** with the checklist above, then report to the operator.

### From 2.1 to 2.2

Push-gate and unpushed-reset-guard: the staging sweep commits locally only, the
pre-integration run owns the push, and the maintainer runs interval-based. On an existing 2.1
installation:

1. Engine and helper update themselves — all logic lives in the repository tree; run
   `--selfcheck --verbose` and expect `SCRIPT_VERSION 2.2.0`.
2. Re-render `../assets/pre-integration-cron-prompt.md.example` (later releases replaced the old
   always-push line with the exact reviewed tip via `--push-reviewed`) and
   `hermes cron edit <pre-integration job> --prompt "$(cat …)"`.
3. Switch the maintainer job to the interval schedule:
   `hermes cron edit <maintainer job> --schedule '0 */4 * * *'`.
4. Nothing else — no hook, consent, shim or state change.

### From 2.2 to 2.3

Monitor-gated maintainer: the maintainer job wakes on the stable pending report instead of
burning idle runs. On an existing 2.2 installation:

1. Helper and engine update themselves — all logic lives in the repository tree; run
   `--selfcheck --verbose` and expect helper `SCRIPT_VERSION 2.3.0`.
2. Render `../assets/maintain-monitor-script.sh.example` to
   `{hermes_home}/scripts/skill-repo-maintain-monitor.sh` (`chmod 755`) and switch the
   maintainer job to the monitor mode:
   `hermes cron edit <maintainer job> --schedule '30m' --monitor-script skill-repo-maintain-monitor.sh`
   (the name is the rendered shim's name under `{hermes_home}/scripts/`). `hermes cron edit`
   knows `--monitor-script`; should a build ever refuse the flag on edit, remove the job and
   re-create it with `hermes cron create … --monitor-script …` instead.
3. The v3 shim passes explicit `--store {store}` and `--repo {maintainer_repo}`; re-render it in
   the 2.3→3.0 step below, not from the 2.3 template copy.
   There is no reset/replay cursor to bootstrap: refresh is ancestry-only and consumption is
   `T ancestor main`.

### From 2.3 to 3.0.0

Explicit bootstrap consent and hook preservation: the installer no longer assumes a fresh install
may start at cursor 0, and it appends the session hook instead of replacing the list. On an
existing 2.3 installation:

1. Engine, core and installer update themselves — all logic lives in the repository tree; run
   `--selfcheck --verbose` and expect `3.0.0` from `SCRIPT_VERSION`, `CORE_VERSION` and
   `INSTALLER_VERSION`. A mismatch is a finding to report, not something to reinstall around.
2. Re-run the installer **without** `--bootstrap-current-ledger`
   (`python3 {skills_repo}/skills/skill-library-maintenance/scripts/install-skill-repo-sync.py --apply-config --machine <name>`):
   the saved cursor is kept and the installer refreshes the `{hermes_home}/bin` engine+core pair
   together. The flag is refused (`12`) whenever state exists — only a fresh install has that
   choice to make.
3. Check `hermes hooks list` before and after: every unrelated `on_session_start` entry and any
   `on_skill_lifecycle` entry is still there; the installer adds only
   `<wrapper> --sync-from-main --hook` and leaves an entry that already runs the wrapper alone.
   A leftover v1 lifecycle maintainer is retired deliberately (empty it and revoke its stale
   consent pair — *From 1.x* step 2); the installer will not clear it for you.
4. Fresh machines only: `--bootstrap-current-ledger` is now mandatory in the installation command.
   Without it the installer exits `12` before writing the wrapper, state, config or file mode.
5. Remove retired modes from local runbooks and cron prompts: `--reset-branch`, `--refresh-strip`,
   `--init-last-pushed`, `--collect`, `--preflight`, `--merge-map` and `--apply-decisions` exit
   `12` with a `retired:` line before any Git call; v3 uses capture → prepare → record-review →
   render/verify-report → integrate instead.

### Update policy

- **The engine pair is installed, not read from the checkout.** The installer copies
  `skill-repo-sync.py` and its shared core `skill_repo_workflow.py` (plus the report template)
  into `{hermes_home}/bin` with identical versions and mode `755`; a missing file or version
  mismatch refuses the install before any wrapper/state write. Update the repository, re-run the
  installer, then verify the installed pair with `--selfcheck`. Replacement errors roll back
  the old pair and report template; the engine refuses mixed core versions rather than running
  a partial upgrade.
- The maintainer helper runs from the repository tree
  (`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-maintain.py
  --store {store} --repo {maintainer_repo} …`); the helper imports the engine beside itself
  (`_engine_candidates`) and the shared core beside both, so no `SKILL_REPO_SYNC_ENGINE` export
  and nothing to refresh under `{hermes_home}/scripts/`.
- The wrapper, the staging shim and the monitor shim are the **only generated artifacts** — each
  exists for a stable path (hook consent; `hermes cron create --script`/`--monitor-script` resolve
  under `{hermes_home}/scripts/`). The wrapper path stays constant across upgrades; its command
  consent pair does not change.
- `--selfcheck` reports observed engine/core/installer versions and any drift; the scripts carry
  `SCRIPT_VERSION` (engine), `CORE_VERSION` (core) and `INSTALLER_VERSION` (installer, must match
  the engine). An engine/core mismatch is a hard refusal (exit 12), not a healthy check with a
  warning. Installer `--version` is available without state, machine identity or bootstrap consent.
  A fresh install additionally needs the explicit `--bootstrap-current-ledger` choice; an upgrade omits it and keeps its cursor. Hook health is not claimed by `--selfcheck` —
  use `hermes hooks doctor`.
- The installer appends its hook entry and never rewrites another profile's hook list: unrelated
  `on_session_start` mappings survive byte-identically and `on_skill_lifecycle` is left alone.
- Later version transitions get their own `From X to Y` checklist here, one section per step —
  append, never rewrite history.
- The pre-integration run is the only pusher; without its run the work stays local (safe, but
  invisible to the maintainer) — hence the window-end schedule. There is no implicit
  catch-up-on-resume: a missed run simply waits for the next schedule or an explicit user trigger.
