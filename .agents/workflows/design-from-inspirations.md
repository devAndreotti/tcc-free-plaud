---
description: Build or review the visual direction of this project using the references stored in `.agents/inspirations`.
---

# Design From Inspirations

Use this workflow when the goal is to derive palette, typography, tone, or component styling from the repository's inspiration set.

## Steps

1. Read:
   - `.agents/skills/inspiration-to-theme/SKILL.md`
   - `docs/Arquitetura_Frontend.md`

2. Inspect:
   - `.agents/inspirations`

3. If the folder is empty:
   - stop and state that there is no visual source material yet

4. If references exist:
   - extract palette
   - extract typography direction
   - define surface and spacing rules
   - turn them into implementation guidance

5. If implementation is requested:
   - produce CSS variables or Tailwind tokens
   - apply them consistently
   - avoid generic AI dashboard styling
