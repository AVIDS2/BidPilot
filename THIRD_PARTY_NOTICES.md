# Third-Party Notices

This repository contains or may contain source adaptations from the following
MIT-licensed projects. The application keeps the original copyright and license
terms for any copied or substantially adapted source files.

## Kiranism next-shadcn-dashboard-starter

- Source: https://github.com/Kiranism/next-shadcn-dashboard-starter
- License: MIT
- Copyright: Kiranism, as stated in the upstream `LICENSE`
- Intended reuse: SaaS workbench shell, sidebar composition, data-table
  interaction patterns, account menu and form composition.
- Excluded: Clerk service integration, upstream brand assets, demo data and
  Next.js-specific routing/server code.

## Ixartz SaaS-Boilerplate

- Source: https://github.com/ixartz/SaaS-Boilerplate
- License: MIT
- Intended reuse: marketing landing-page section organization and SaaS
  authentication/team information architecture.
- Excluded: Clerk, Drizzle, Next.js server implementation, demo copy and
  upstream media assets.

## nextjs/saas-starter

- Source: https://github.com/nextjs/saas-starter
- License: MIT
- Intended reuse: compact marketing and account-page composition where it fits
  BidPilot's existing API contracts.
- Excluded: Stripe and Next.js Server Actions implementation.

## shadcn/ui

- Documentation and component registry: https://ui.shadcn.com/docs/components
- Components are generated into this repository as source and are used under
  the project's configured Base UI and Tailwind CSS setup.

## Not reused

Midday is not a source dependency for this project. Its current repository is
AGPL-3.0 and its official documentation describes separate commercial licensing
requirements.

## README presentation assets

The README presentation artwork under `assets/` was adapted from the README
visual assets in [AVIDS2/memorix](https://github.com/AVIDS2/memorix), an
Apache-2.0 licensed project. The adapted source snapshot is
[`2853a1b`](https://github.com/AVIDS2/memorix/tree/2853a1b48008af56989a0709bcc389bd635a66b3).
The adapted files are `assets/readme-hero.svg`
and the graphical section-title assets under `assets/tags/`. Their product
labels were changed for BidPilot; no Memorix runtime code, product claims, or
provider configuration is included. The README structure research and source
revisions are recorded in
[`docs/research/readme-product-narrative-study.md`](docs/research/readme-product-narrative-study.md).
