# Understand Anything Dev Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install `Understand-Anything` locally and document a minimal daily-report developer workflow for project navigation and change-impact review.

**Architecture:** Treat `Understand-Anything` as a local developer companion only. The implementation adds local tool installation, a project analysis ignore file, and one workflow note; it does not alter report generation, trading decisions, snap-ui export, or wiki graph analysis.

**Tech Stack:** Bash installer from `Lum1104/Understand-Anything`, Markdown documentation, `.understand-anything/.understandignore`, Git verification commands.

---

### Task 1: Install Or Update Local Plugin

**Files:**
- External: `$HOME/.understand-anything/repo`
- External: `$HOME/.understand-anything-plugin`
- External: `$HOME/.agents/skills/understand*`
- External: `$HOME/.hermes/skills/understand-anything`

- [x] **Step 1: Install for Codex**

Run:

```bash
bash /tmp/codex-understand-anything/install.sh codex
```

Expected: command exits 0 and reports that skills were linked under `$HOME/.agents/skills`.

- [x] **Step 2: Install for Hermes**

Run:

```bash
bash /tmp/codex-understand-anything/install.sh hermes
```

Expected: command exits 0 and reports a folder link under `$HOME/.hermes/skills/understand-anything`.

- [x] **Step 3: Verify plugin links**

Run:

```bash
test -L "$HOME/.understand-anything-plugin"
test -L "$HOME/.agents/skills/understand"
test -L "$HOME/.agents/skills/understand-diff"
test -L "$HOME/.agents/skills/understand-dashboard"
test -L "$HOME/.hermes/skills/understand-anything"
```

Expected: all commands exit 0.

- [x] **Step 4: Inspect installed skill metadata**

Run:

```bash
head -n 20 "$HOME/.agents/skills/understand/SKILL.md"
head -n 20 "$HOME/.agents/skills/understand-diff/SKILL.md"
head -n 20 "$HOME/.agents/skills/understand-dashboard/SKILL.md"
```

Expected: each file starts with skill metadata for the matching `Understand-Anything` skill.

### Task 2: Add Project Analysis Ignore Rules

**Files:**
- Modify: `.gitignore`
- Create: `.understand-anything/.understandignore`

- [x] **Step 1: Keep generated graph artifacts local in Git**

Add these lines near the existing local generated output rules in `.gitignore`:

```gitignore
/.understand-anything/*
!/.understand-anything/.understandignore
```

- [x] **Step 2: Create the ignore file**

Create `.understand-anything/.understandignore` with:

```gitignore
# Local VCS and generated project analysis artifacts
.git/
.understand-anything/intermediate/
.understand-anything/tmp/
.understand-anything/diff-overlay.json

# Daily-report runtime artifacts
.generated/
.worktrees/
reports/
replay/
data/
snapshots/
logs/

# Local UI copies and publish workspaces
snap-ui/
snap-ui-remote-*/

# Local environments and machine-specific state
.env
.hermes/
venv/
.venv/
wiki/.obsidian/
wiki/*.canvas
.DS_Store

# Python caches
__pycache__/
**/__pycache__/
*.pyc
*.pyo

# Local tool caches
scripts/cache/
scripts/data/
scripts/.workbuddy/
scripts/.codebuddy/

# Heavy or non-source assets
*.png
*.jpg
*.jpeg
*.gif
*.svg
*.ico
*.woff
*.woff2
*.ttf
*.eot
*.mp3
*.mp4
*.pdf
*.zip
*.tar
*.gz
*.min.js
*.min.css
*.map
```

- [x] **Step 3: Verify the file content**

Run:

```bash
cat .understand-anything/.understandignore
```

Expected: output includes `reports/`, `data/`, `.generated/`, `snap-ui/`, and `.understand-anything/intermediate/`.

### Task 3: Add Developer Workflow Note

**Files:**
- Create: `docs/ops/understand-anything-dev-flow.md`

- [x] **Step 1: Create the workflow note**

Create `docs/ops/understand-anything-dev-flow.md` with:

```markdown
# Understand Anything Dev Flow

Date: 2026-05-25
Scope: local developer navigation for `a-daily-report`

## Purpose

`Understand-Anything` is a local helper for navigating this project and reviewing the effect of code changes. It is not part of daily report generation and is not a source for trading conclusions.

## Use Modes

### Project Navigation

Use the project graph when you need to understand where a report concept, renderer, data source, selection step, or audit check lives.

Recommended flow:

1. Refresh the project graph after meaningful source changes.
2. Open the dashboard when a visual overview helps.
3. Use graph context to find relevant files, then verify behavior with the repo's normal tests and replay artifacts.

### Change-Impact Review

Use change-impact review after a non-trivial diff, especially when edits touch report rendering, selection, market-state, data-source, decision-ledger, or snap-ui export code.

Recommended flow:

1. Review the Git diff.
2. Run the graph-based diff review.
3. Inspect affected components before final verification.
4. Run the relevant Python 3.14 tests or replay checks required by the changed modules.

### Local-Only Exploration

The graph, dashboard data, intermediate files, and diff overlay are local helper artifacts. Do not treat them as report source data, and do not publish them unless a later reviewed design explicitly changes that.

## Boundaries

- Do not put graph summaries into the report body.
- Do not use the graph to decide participation, position, cancellation, or final report conclusions.
- Do not let graph output override deterministic facts, bounded reasoning payloads, tests, replay output, or human review.
- Do not use this workflow as a substitute for the report contract or data-source contract.

## Local Artifacts

- `.understand-anything/knowledge-graph.json`: local project graph if generated.
- `.understand-anything/domain-graph.json`: local domain graph if generated later.
- `.understand-anything/diff-overlay.json`: local dashboard overlay for changed and affected files.
- `.understand-anything/intermediate/`: temporary working files.
- `.understand-anything/tmp/`: temporary validation scripts.

By default, generated graph artifacts stay local.
```

- [x] **Step 2: Check wording boundaries**

Run:

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path

text = Path("docs/ops/understand-anything-dev-flow.md").read_text(encoding="utf-8")
blocked = [
    "".join(map(chr, [30828, 38376, 31105])),
    "".join(map(chr, [38376, 31105])),
    "".join(map(chr, [103, 97, 116, 101])),
    "".join(map(chr, [104, 97, 114, 100, 32, 103, 97, 116, 101])),
    "".join(map(chr, [29366, 24577, 26426])),
    "".join(map(chr, [29366, 24577, 26426, 35789, 27719])),
]
matches = [word for word in blocked if word in text]
if matches:
    raise SystemExit("wording contract failed")
PY
```

Expected: command exits 0.

### Task 4: Verify Scope And Commit

**Files:**
- Verify: `.gitignore`
- Verify: `.understand-anything/.understandignore`
- Verify: `docs/ops/understand-anything-dev-flow.md`
- Verify: `docs/superpowers/plans/2026-05-25-understand-anything-dev-flow.md`

- [x] **Step 1: Verify no report-generation files changed**

Run:

```bash
git diff --name-only
```

Expected: the scoped implementation diff only includes `.gitignore`, `.understand-anything/.understandignore`, `docs/ops/understand-anything-dev-flow.md`, and this plan file, plus any pre-existing unrelated worktree changes outside this task.

- [x] **Step 2: Verify ignored generated paths**

Run:

```bash
git check-ignore -v reports/example.md data/example.json snapshots/example.json logs/example.log .generated/example.json snap-ui/package.json .understand-anything/knowledge-graph.json
```

Expected: each path is reported as ignored by `.gitignore` or `.understand-anything/.understandignore` where the command is applicable.

- [x] **Step 3: Verify local plugin install**

Run:

```bash
test -L "$HOME/.understand-anything-plugin" && readlink "$HOME/.understand-anything-plugin"
test -L "$HOME/.agents/skills/understand" && readlink "$HOME/.agents/skills/understand"
test -L "$HOME/.hermes/skills/understand-anything" && readlink "$HOME/.hermes/skills/understand-anything"
```

Expected: each link resolves into `$HOME/.understand-anything/repo/understand-anything-plugin`.

- [x] **Step 4: Stage scoped files**

Run:

```bash
git add .gitignore .understand-anything/.understandignore docs/ops/understand-anything-dev-flow.md docs/superpowers/plans/2026-05-25-understand-anything-dev-flow.md
```

Expected: only these task files are newly staged by this command.

- [x] **Step 5: Commit scoped files**

Run:

```bash
git commit -m "chore: add understand-anything dev flow"
```

Expected: commit succeeds with the scoped files.
