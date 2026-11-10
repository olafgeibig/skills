# Install & Update

Bring an installation of the Stage & Consolidate sync into being — a new machine or a new
profile on an existing one — and move an existing installation between versions. Mechanics, run
books and diagnosis live in `shared-repo-sync.md`; the renderable prompts and blocks in
`../assets/`. Roles do not come from this file: the installation's own identity (`SOUL.md` or its
`hermes-profile-*` skill) says which role it plays.

## Roles

**What lands on a transport branch is always pre-consolidated: the staging sweep commits locally,
the pre-consolidation run owns the push, the consolidator only ever sees cleaned content.**

Exactly two, and they differ in one job only:

| Role | Who | Writes `main`? | Jobs |
|---|---|---|---|
| **Consolidator** | exactly one machine in the whole setup | yes — the only writer | staging sweep · pre-consolidation · consolidation (monitor-gated) |
| **Contributor** | every other installation | never | staging sweep · pre-consolidation |

Both run the hourly staging sweep (bundles pending work into one transport commit on
`machine/<host>`, locally — no push) and the daily pre-consolidation at 03:30 (the instance
cleans its own pending net: instance-shaped lessons out of canonical skills, valuable ones into
the profile's adaptation; then it pushes). Only the Consolidator additionally runs the
monitor-gated consolidation (a 30 min tick — the agent wakes only when a transport branch has
new content) — it
consumes the transport branches and lands them on `main`, one commit per consumed branch
(*Consolidator run book* in `shared-repo-sync.md`).

## Installation (new)

### Values

Four, and the agent already knows where to find them:

- `{machine}` — the logical name from the machine table in `hermes-projects` (verify with `hostname`)
- `{skills_repo}` — the shared checkout's entry in `hermes config get skills.external_dirs`
- `{hermes_home}` — `$HERMES_HOME`
- `{scratch_dir}` — `{hermes_home}/cache/scratch/consolidate-lauf` (create once)

### Templates to render

Replace the `{var}` placeholders (each template's header comment lists its own variables — that
list is the template contract):

| Template | Renders to |
|---|---|
| `../assets/stage-sweep-script.sh.example` | `{hermes_home}/scripts/skill-repo-sync-stage.sh` (`chmod 755`) |
| `../assets/consolidate-monitor-script.sh.example` | `{hermes_home}/scripts/skill-repo-consolidate-monitor.sh` (`chmod 755`) |
| `../assets/pre-consolidation-cron-prompt.md.example` | the pre-consolidation job prompt |
| `../assets/consolidator-cron-prompt.md.example` | the consolidation job prompt (Consolidator only) |
| `../assets/soul-instance-block.md.example` | the identity block in `{hermes_home}/SOUL.md` (or the profile skill) |

### Components and jobs

| Piece | What | Roles |
|---|---|---|
| `on_session_start` hook | `--sync-from-main` via the wrapper | both |
| Wrapper | `{hermes_home}/bin/skill-repo-sync` — generated; the stable path hook consent binds to | both |
| State | `{hermes_home}/skill-repo-sync.json` | both |
| Shim | `{hermes_home}/scripts/skill-repo-sync-stage.sh` — generated (see table above) | both |
| Monitor shim | `{hermes_home}/scripts/skill-repo-consolidate-monitor.sh` — generated (see table above); prints the byte-stable pending report (`--pending`) for the consolidator job's monitor gate | Consolidator only |
| Staging sweep | hourly `:07` — bundles locally (no push); `no_agent`, shim, deliver telegram | both |
| Pre-consolidation | `30 3 * * *` — cleans and pushes; agent, skills `skill-governance` + `skill-library-maintenance` | both (per profile on a multi-profile machine) |
| Consolidation | monitor-gated (30 min tick; the agent wakes only when the pending report changes — no idle LLM runs); a fixed nightly slot is not required. Agent, skill `skill-library-maintenance` | Consolidator only |

### Steps

1. **Render the templates** (values above) and place them at their targets.
2. **Create the jobs** (names, schedule and `--provider`/`--model`/`--pin` per local decision; the
   prompts are the rendered files):

   ```bash
   hermes cron create '7 * * * *' --no-agent --script skill-repo-sync-stage.sh \
     --name "skill-repo staging sweep (hourly)" --deliver telegram --workdir {skills_repo}
   # pre-consolidation: schedule at the end of the machine's typical usage window
   # (catch-up on resume covers missed runs)
   hermes cron create '30 3 * * *' "$(cat rendered-pre-consolidation-prompt.txt)" \
     --name "skill-repo pre-consolidation (instance review)" \
     --skill skill-governance --skill skill-library-maintenance \
     --provider <P> --model <M> --pin --deliver telegram --workdir {skills_repo}
   # Consolidator only — monitor-gated: the shim's byte-stable --pending report wakes the agent
   # only on change. --monitor-script takes the rendered shim's NAME under {hermes_home}/scripts/.
   hermes cron create '30m' "$(cat rendered-consolidator-prompt.txt)" \
     --name "skill-repo consolidator (monitor-gated)" \
     --skill skill-library-maintenance \
     --monitor-script skill-repo-consolidate-monitor.sh \
     --provider <P> --model <M> --pin --deliver telegram --failure-deliver telegram \
     --workdir {skills_repo}
   ```

   The model pin is mandatory for agent jobs: an unpinned job resolves the config route at fire
   time and fails closed when `model.*` changes underneath it (*Crons* in `shared-repo-sync.md`).
3. **Installer.**
   `python3 {skills_repo}/skills/skill-library-maintenance/scripts/install-skill-repo-sync.py --apply-config --machine <name>`
   — add `--bootstrap-current-ledger` on a fresh install only (skips historical ledger entries);
   an existing install keeps its cursor. The installer registers the `on_session_start` hook;
   approve its `(event, command)` pair through the normal consent flow.
4. **Record the identity** — the rendered `SOUL.md` block (or a line in the profile's
   `hermes-profile-*` skill), so a fresh session knows its role and machine without asking.

### Verification

- `python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-sync.py --selfcheck --verbose`
  — installed state, and the `SCRIPT_VERSION` header matches the other machines (drift is a
  finding, see the deployment audit in `shared-repo-sync.md`).
- `hermes hooks list && hermes hooks doctor` — the `(event, command)` pair allowlisted and healthy;
  configured is not activated.
- `hermes cron list` — the expected jobs (two, plus consolidation on the Consolidator) with the
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
   machine/<name>` (the consolidated tip). If the local branch still carries consumed commits,
   reset it to `origin/machine/<name>` — backup the old tip with a `backup/` ref first; never
   discard work silently.
2. **Retire the v1 jobs and the v1 hook.** `hermes cron list`, then `hermes cron remove <id>` for
   the paused "skill-repo-sync safety" and "skill-library monthly audit" jobs — they invoke
   retired v1 modes (`--safety`, `--audit`) and only produce noise. If `hermes hooks list` still
   shows the retired `on_skill_lifecycle` publisher hook (v1 fired it per skill write), empty it
   (`hermes config set hooks.on_skill_lifecycle '[]'`) and revoke its stale consent pair
   (`hermes hooks revoke <wrapper path>`, then let the installer's pair re-consent in the next
   step) — only `on_session_start` survives, and keeping the dead pair approved is just confusion
   fuel.
3. **Installation steps** above (render, jobs, installer with `--apply-config --machine <name>`,
   identity record).
4. **Verify** with the checklist above, then report to the operator.

### From 2.1 to 2.2

Push-gate and unpushed-reset-guard: the staging sweep commits locally only, the
pre-consolidation run owns the push, and the consolidator runs interval-based. On an existing 2.1
installation:

1. Engine and helper update themselves — all logic lives in the repository tree; run
   `--selfcheck --verbose` and expect `SCRIPT_VERSION 2.2.0`.
2. Re-render `../assets/pre-consolidation-cron-prompt.md.example` (it now ends with the
   always-push line) and `hermes cron edit <pre-consolidation job> --prompt "$(cat …)"`.
3. Switch the consolidator job to the interval schedule:
   `hermes cron edit <consolidator job> --schedule '0 */4 * * *'`.
4. Nothing else — no hook, consent, shim or state change.

### From 2.2 to 2.3

Monitor-gated consolidator + Refresh-Strip: the consolidator job wakes on a
byte-stable pending report instead of burning idle runs, and pre-consolidation step 0 replays
never-pushed commits onto the refreshed strip (`last_pushed_tip`). On an existing 2.2
installation:

1. Helper and engine update themselves — all logic lives in the repository tree; run
   `--selfcheck --verbose` and expect helper `SCRIPT_VERSION 2.3.0`.
2. Render `../assets/consolidate-monitor-script.sh.example` to
   `{hermes_home}/scripts/skill-repo-consolidate-monitor.sh` (`chmod 755`) and switch the
   consolidator job to the monitor mode:
   `hermes cron edit <consolidator job> --schedule '30m' --monitor-script skill-repo-consolidate-monitor.sh`
   (the name is the rendered shim's name under `{hermes_home}/scripts/`). `hermes cron edit`
   knows `--monitor-script`; should a build ever refuse the flag on edit, remove the job and
   re-create it with `hermes cron create … --monitor-script …` instead.
3. Re-render `../assets/pre-consolidation-cron-prompt.md.example` (it now carries the
   refresh-strip rule) and `hermes cron edit <pre-consolidation job> --prompt "$(cat …)"`.
4. `last_pushed_tip` initializes itself on the first `--refresh-strip` — no manual state edit.
   Stale base is the normal case: a laptop waking after the daily pre-consolidation/consolidation cycle is always behind
   the strip by design, and step 0 (refresh-strip) makes it fresh again.

### Update policy

- **No copies of the Python scripts.** Every call goes directly into the repository tree
  (`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py …`);
  the helper imports the engine beside itself (`_engine_candidates`), so no `SKILL_REPO_SYNC_ENGINE`
  export and nothing to refresh under `{hermes_home}/scripts/`.
- The wrapper, the staging shim and the monitor shim are the **only generated artifacts** — each
  exists for a stable path (hook consent; `hermes cron create --script`/`--monitor-script` resolve
  under `{hermes_home}/scripts/`). All logic
  lives in the repository; update it there and the wrapper picks the change up on its next exec.
- `--selfcheck` reports a version mismatch; the scripts carry `SCRIPT_VERSION` (engine and helper)
  and `INSTALLER_VERSION` (installer, must match the engine).
- Later version transitions get their own `From X to Y` checklist here, one section per step —
  append, never rewrite history.
- The pre-consolidation run is the only pusher; without its run the work stays local (safe, but
  invisible to the consolidator) — hence catch-up-on-resume and the window-end schedule.
