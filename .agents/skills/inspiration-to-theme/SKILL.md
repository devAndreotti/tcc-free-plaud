---
name: inspiration-to-theme
description: Use when designing the UI of this repository based on visual references stored in `.agents/inspirations`. Extract palette, typography, spacing, surfaces, layout rhythm, and component tone from the inspirations and turn them into concrete design guidance, tokens, and implementation direction. Trigger when the user mentions inspirations, palette, theme, visual direction, design system, or asks to make the interface follow the references in this repo.
---

# Inspiration to Theme

## Purpose

Turn real visual references from this repository into a usable design direction.

This skill exists to avoid:

- generic AI dashboard design
- random color picking
- styling detached from the chosen references

## Inputs

Primary source:

- `D:\Dev\Repos\tcc-free-plaud\.agents\inspirations`

Project context:

- `docs/Arquitetura_Frontend.md`
- current UI files, if they exist

## Workflow

### 1. Audit the inspiration set

Inspect the files inside `.agents/inspirations`.

If the folder is empty:

- stop
- say there is no visual source material yet
- ask for 3 to 10 strong references or proceed with a documented fallback direction

### 2. Extract the visual system

For each useful reference, identify:

- dominant colors
- accent colors
- contrast profile
- typography style
- spacing density
- border radius tendency
- surface treatment
- visual hierarchy
- motion tone

Do not stop at "looks modern".
Name the actual characteristics.

### 3. Synthesize a project theme

Produce:

1. a short visual thesis in plain language
2. a palette with role-based colors
3. typography guidance
4. spacing and surface rules
5. component rules for cards, panels, inputs, buttons, tables and chat blocks

### 4. Translate into implementation

When asked to implement, convert the direction into:

- CSS variables
- Tailwind tokens
- component styling rules
- layout constraints

Keep the result coherent with the product:

- local-first
- trustworthy
- technical
- research-oriented

## Required Output Shape

When this skill is used for planning or review, structure the answer as:

### Visual Thesis

1 short paragraph.

### Palette

- background
- surface
- text
- muted text
- border
- accent
- success / warning / error if relevant

### Typography

- heading direction
- body direction
- sizing mood

### UI Rules

- cards
- forms
- chat
- benchmark/results

### Risks

- what would make the implementation drift away from the inspirations

## Constraints

1. Do not invent that the design came from inspirations if the folder is empty.
2. Do not mimic a single reference literally.
3. Prefer a small, controlled token set over ornamental styling.
4. Keep the interface readable and defensible for a TCC product.

## Related Files

- `.agents/inspirations/README.md`
- `docs/Arquitetura_Frontend.md`
