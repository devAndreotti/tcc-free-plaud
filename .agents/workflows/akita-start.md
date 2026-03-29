---
description: Kick off work in this repository using the documented Akita-inspired development flow and git strategy.
---

# Akita Start

Use this workflow when starting a new implementation cycle in this repository.

## Goal

Start work without skipping architecture, test strategy, or git discipline.

## Steps

1. Read:
   - `CLAUDE.md`
   - `docs/Arquitetura.md`
   - `docs/Arquitetura_Backend.md`
   - `docs/Arquitetura_Frontend.md`
   - `docs/Metodologia_Akita_Git.md`
   - `docs/Plano_de_Arranque.md`

2. Confirm the current slice:
   - `feat/pipeline-core`
   - `feat/rag-benchmark`
   - `feat/audio-ingest`
   - `feat/desktop-shell`

3. Before coding:
   - define the smallest testable slice
   - define the branch
   - define the expected artifact

4. During implementation:
   - keep changes narrow
   - update docs when architecture shifts
   - commit per relevant decision

5. Before closing the slice:
   - run tests
   - review diff
   - update docs if needed
   - decide whether this is tag-worthy

## Reminder

The project must prove the experimental pipeline first.
Do not start with desktop polish.
