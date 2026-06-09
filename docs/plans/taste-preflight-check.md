# BidPilot taste-skill Pre-Flight Check

## Design Read
**B2B SaaS for technical buyers, Linear-style minimalist, shadcn + Tailwind v4 + Geist.**

## Dials
- DESIGN_VARIANCE: 5
- MOTION_INTENSITY: 3
- VISUAL_DENSITY: 5

## Pre-Flight Checklist

### Layout & Hero
- [ ] Hero fits viewport (headline ≤ 2 lines, subtext ≤ 20 words)
- [ ] Hero top padding ≤ pt-24
- [ ] Hero stack max 4 text elements
- [ ] No scroll cues ("Scroll", "↓ scroll")
- [ ] Navigation on ONE line at desktop, height ≤ 80px

### Design System
- [ ] ONE design system (shadcn/ui) — no mixing
- [ ] Color consistency lock: one accent across all sections
- [ ] Shape consistency lock: one corner-radius system (0.625rem)
- [ ] No AI-purple gradients
- [ ] No pure black (#000000) — use off-black

### Typography
- [ ] Geist font (not Inter)
- [ ] No serif as default
- [ ] No oversized H1s
- [ ] Italic descender clearance (leading-[1.1] + pb-1)

### Content
- [ ] ZERO em-dashes (—) anywhere
- [ ] No fake-precise numbers (92%, 4.1×)
- [ ] No generic names (Jane Doe, Acme)
- [ ] No filler verbs (Elevate, Seamless, Unleash)
- [ ] Copy self-audit: every visible string re-read

### Layout Diversity
- [ ] ≤ ceil(sectionCount/3) eyebrows
- [ ] No 3+ consecutive image+text splits
- [ ] No section-layout-repetition (4+ families across 8 sections)
- [ ] No 3-equal feature cards
- [ ] No split-header pattern as default

### Cards & Visual
- [ ] No div-based fake screenshots
- [ ] No broken image links
- [ ] Real images or explicit placeholders
- [ ] Cards only where elevation communicates hierarchy

### Accessibility
- [ ] Button contrast check (WCAG AA 4.5:1)
- [ ] Form contrast check
- [ ] Reduced motion honored (MOTION_INTENSITY > 3)
- [ ] Dark mode tokens defined and tested

### Performance
- [ ] LCP < 2.5s
- [ ] INP < 200ms
- [ ] CLS < 0.1
- [ ] Viewport stability (min-h-[100dvh], not h-screen)

### Anti-Slop
- [ ] No Inter font
- [ ] No AI-purple
- [ ] No three-equal cards
- [ ] No "Quietly in use at"
- [ ] No version labels in hero (V0.6, BETA)
- [ ] No section-numbering eyebrows (00/INDEX)
- [ ] No decorative colored dots
- [ ] No em-dash
- [ ] No "Trusted by" inside hero
- [ ] No locale/weather strips

## Status
**Pending** — Run this check after Sprint 3 landing page redesign is complete.
