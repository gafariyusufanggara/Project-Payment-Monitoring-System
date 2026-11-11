# Stack — Next.js / React

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk npx eslint .` | `rtk npx tsc --noEmit` | `rtk npx vitest run` | `rtk npm run build` |

Biome instead of ESLint: `rtk npx biome check .`. Run the `package.json` test
script when it exists; use vitest/jest only when it is in `devDependencies`.

## Anti-slop

- Server Components by default; `"use client"` only for real interaction or
  browser APIs.
- Data fetching in a Server Component or Route Handler, never `useEffect`.
- Never `<img>`: use `next/image` with explicit `width`/`height` or `fill` plus
  a sized parent.
- Fonts via `next/font`, never a raw `<link>` to Google Fonts.

## shadcn/ui

Only when `components.json` exists. Components are owned source: edit in place.
Never restyle with `!important`; change the token. If a shadcn MCP server is
configured, query it before hand-writing a component; otherwise read the existing
components and say the MCP was unavailable.
