# Stack — Astro

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk npx eslint .` | `rtk npx astro check` | `rtk npx vitest run` | `rtk npm run build` |

Biome instead of ESLint: `rtk npx biome check .`. Run the `package.json` test
script when it exists; use vitest/jest only when it is in `devDependencies`.

## Anti-slop

- Zero JS by default. `client:load` only when hydration is proven necessary.
- Islands over a page-wide SPA.
- Match the project's existing token and component conventions.
