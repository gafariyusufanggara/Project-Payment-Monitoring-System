# Stack — Vite SPA (React / Vue)

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk npx eslint .` | `rtk npx tsc --noEmit` | `rtk npx vitest run` | `rtk npm run build` |

Biome instead of ESLint: `rtk npx biome check .`. Run the `package.json` test
script when it exists; use vitest/jest only when it is in `devDependencies`.

## Anti-slop

- No SSR or server-component assumptions; the app is client-rendered.
- Data fetching belongs in the existing query/state layer, not ad-hoc effects.
- Match the project's existing token and component conventions.
