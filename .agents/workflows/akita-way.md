---
description: Full XP + AI development workflow based on Fabio Akita's methodology
---

# Akita Way — Extreme Programming with AI

A complete development workflow where the AI is your pair programmer, following XP principles.
The core idea: **you build the skeleton, the AI fills in the organs.**

> [!IMPORTANT]
> Before your first project, run `/ai-jail` once to understand agent limits and set governance rules.

## Guardrails — Inviolable Rules
- **Test BEFORE code** — first prompt is always a test, never a feature
- **CLAUDE.md BEFORE any code** — architecture defined before the first line
- **Never delegate architecture** — you decide the skeleton, AI implements
- **Files max ~300 lines** — refactor immediately if exceeded
- **CI green = advance. CI red = STOP** — no exceptions, no shortcuts
- **Small releases** — commit every functional feature, never accumulate
- **Review every diff** — unreviewed AI code is nobody's code

---

## Phase 1: Skeleton — Architecture & CLAUDE.md

> Akita Day 2: "The exercise of the WHYs"

Before writing ANY code, think and document the entire architecture.

### Step 1 — Define Stack with Justifications
Answer the WHYs for every technology choice:
- Why this language? Why this framework? Why this database?
- Why monorepo or polyrepo? Why this hosting?
- Document trade-offs considered and rejected alternatives.

### Step 2 — Create CLAUDE.md
Create a `CLAUDE.md` file in the project root using the template at the end of this workflow.
This is the **living spec** — the agent reads it before every session.

Minimum sections:
1. Project overview and architecture
2. Technology stack (with versions)
3. Directory structure
4. Layers and responsibilities (handler → service → repository → model)
5. Code conventions (file size, naming, comments)
6. Environment variables
7. What NEVER to do

### Step 3 — Scaffold Project Structure
→ Use `/new-project` to scaffold based on your stack choice.
→ Use `/architecture` to create architecture diagrams.
→ Use `/env-config` to set up environment variables.
→ Use `/docker` if containerizing.

### Step 4 — Connect Dependencies
- Set up database connections
- Configure Docker Compose
- Set up third-party API connections
- Verify everything connects before writing business logic

**GATE:** Do NOT proceed until CLAUDE.md exists and project structure is scaffolded.

---

## Phase 2: TDD Foundation

> Akita Day 3: "I know the services, the back/front separation, every feature. Time for tests."

### Step 5 — Map Features as Test Scenarios
For every planned feature, describe the expected behavior as tests:
- Input → expected output
- Edge cases (null, empty, boundary)
- Error scenarios

### Step 6 — Write Tests BEFORE Code
→ Use `/unit-test` to write unit tests.
→ Use `/e2e-test` or `/playwright-test` for integration/E2E tests.

Rules:
- If the AI suggests a function without a test, **reject it immediately**.
- Every feature has a contract expressed as a test.

### Step 7 — Set Up CI
→ Use `/ci-cd` to configure continuous integration.

CI must run on every commit:
- Linting
- Unit tests
- Integration tests (if applicable)
- Security audit

**GATE:** Tests are written and CI is green before ANY implementation code.

---

## Phase 3: Coding — Make Tests Pass

> Akita Day 4: "Write code that passes the Day 3 tests."

### Step 8 — Implement Features TDD-Style
For each feature, follow the Feature Loop (see below).
→ Use `/new-feature` for full feature implementation.
→ Use `/git-commit` for conventional commits.

Rules:
- Implement in priority order
- Don't optimize prematurely — make it work first
- Commit at every functional feature (small releases)
- CI green = advance. CI red = stop and fix.

**GATE:** All planned tests pass. CI is green.

---

## Phase 4: Optimization & Refactoring

> Akita Day 5: "Tests pass but it's not polished? Time to refactor."

### Step 9 — Identify Bottlenecks
- Profile slow code paths
- Find N+1 queries, expensive loops
- Evaluate: async jobs? Event architecture? Message queues?

### Step 10 — Refactor
→ Use `/refactor` to improve code quality.
→ Use `/performance` to optimize hot paths.

Questions to ask:
- Does this MCP make more sense as a REST API? A background job?
- Can this be cached? Should it be async?

### Step 11 — Document Optimization Decisions
Update CLAUDE.md with any new architectural decisions or conventions learned.

**GATE:** Tests still pass after all refactoring. No behavior changes.

---

## Phase 5: Interface

> Akita Day 6: "The output doesn't have to be React."

### Step 12 — Choose the Right Interface
The best interface depends on the product:
- Web app → `/dashboard-ui` or `/landing-page`
- Components → `/new-component`
- Discord bot → custom implementation
- CLI → `/cli-tool`
- Mobile → React Native or similar

### Step 13 — Implement Presentation Layer
→ Use the appropriate workflow for your chosen interface.
→ Use `/playwright-test` for web UI testing using Playwright MCP.

Integrate with the already-tested API layer.

**GATE:** Interface works with real data. UI tests pass.

---

## Phase 6: Deploy & CI/CD Pipeline

> Akita Day 7: "Structure the deploy pipeline. The sky is the limit."

### Step 14 — Production Pipeline
→ Use `/ci-cd` to configure the full pipeline.
→ Use `/security-audit` for vulnerability scanning.
→ Use `/dependency-check` for dependency audit.

Pipeline must include:
- Linting (ESLint, Pylint, golangci-lint, Clippy — whatever fits the stack)
- Tests (unit + integration + E2E)
- Security audit
- Build
- Deploy

### Step 15 — Deploy
→ Use `/deploy`, `/vercel-deploy`, `/railway-deploy`, or `/docker` depending on target.

### Step 16 — Verify Production
- Smoke test in production
- Monitor logs for first 24h
- Verify with real users if possible

**GATE:** Application is deployed and accessible. CI/CD runs automatically on push.

---

## Feature Loop — Anatomy of a Feature with AI

Use this loop for EVERY new feature after initial development:

```
┌─ 1. Write the test first
│     Define expected behavior BEFORE any code.
│     This gives the agent a clear contract to fulfill.
│
├─ 2. Short, specific prompt
│     Don't try to do everything at once.
│     One thing at a time. Agent performs better on small, well-defined tasks.
│
├─ 3. Review the diff critically
│     YOU are the human pair. Read the generated code.
│     If you don't understand it, don't accept it.
│
├─ 4. Run the tests
│     CI must run automatically.
│     Green = safe to advance. Red = fix before continuing.
│
├─ 5. Commit immediately
│     Small releases. Don't accumulate.
│     Each functional feature = one commit. Clean history = clear mental model.
│
└─ 6. Update CLAUDE.md
      If you learned something new in this feature, document it.
      The agent will remember next session.
```

---

## Weekly Review Checklist

Run this every week (or at natural project milestones):

- [ ] **Test coverage:** Is it growing or stagnating?
- [ ] **Average file size:** Any files crossing 300 lines?
- [ ] **CLAUDE.md health:** Remove obsolete rules, add new learnings
- [ ] **Real data testing:** Are tests running against real scenarios or just mocks?
- [ ] **Tech debt:** Anything deferred that's becoming painful?
- [ ] **Agent performance:** Is context degrading? Time for a fresh session?

---

## CLAUDE.md Template

Copy and adapt this template for every new project:

```markdown
# CLAUDE.md — [Project Name]

## Overview
Brief description of the project and its purpose.

## Stack
- Backend: [language + framework + version]
- Frontend: [framework + version]
- Database: [database + version]
- Cache: [if applicable]
- Jobs: [if applicable]
- Deploy: [platform]

## Directory Structure
[project-specific directory tree]

## Layers & Responsibilities
- **Handler/Controller:** Receives HTTP, validates input, calls service
- **Service:** Business logic, orchestration
- **Repository:** Database access, queries
- **Model:** Data entities, validations

> NEVER access the database directly from a handler/controller.

## Code Conventions
- Files: max ~300 lines. Refactor if exceeded.
- Functions: max ~30 lines.
- Names: English.
- Comments: Portuguese when explaining non-obvious decisions.
- Commit format: conventional commits (feat/fix/test/refactor/docs)

## Environment Variables
List all required env vars with descriptions.
Keep `.env.example` always updated.

## Jobs & Background Processing
[If applicable — describe async job conventions, timeouts, DLQ rules]

## What NEVER to Do
- Never commit `.env` files
- Never commit without passing tests
- Never create files above 300 lines without refactoring
- Never merge without CI green
- Never make architectural decisions without human approval
- Never hardcode secrets
```

---

## Quick Reference

| Phase | Focus | Gate | Delegates to |
|-------|-------|------|-------------|
| 1. Skeleton | Architecture + CLAUDE.md | CLAUDE.md exists, project scaffolded | `/new-project`, `/architecture`, `/env-config`, `/docker` |
| 2. TDD Foundation | Tests before code | Tests written, CI green | `/unit-test`, `/e2e-test`, `/ci-cd` |
| 3. Coding | Make tests pass | All tests pass | `/new-feature`, `/git-commit` |
| 4. Optimization | Refactor + performance | Tests still pass | `/refactor`, `/performance` |
| 5. Interface | Presentation layer | UI works with real data | `/dashboard-ui`, `/landing-page`, `/playwright-test` |
| 6. Deploy | CI/CD + production | App deployed, pipeline automatic | `/ci-cd`, `/security-audit`, `/deploy` |
| Feature Loop | Per-feature TDD cycle | Test → Code → Review → Commit | — |
| Weekly Review | Project health check | Checklist complete | — |

## Reference
- Source: [Do Zero à Pós-Produção — Akita](https://akitaonrails.com/2026/02/20/do-zero-a-pos-producao-em-1-semana)
- Prerequisite: `/ai-jail` (run once before first project)
- Related: `/superpowers` (obra/superpowers workflow — complementary)
