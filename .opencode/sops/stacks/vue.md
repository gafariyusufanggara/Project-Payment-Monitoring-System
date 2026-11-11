# Stack — Vue / Nuxt

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk npx eslint .` | `rtk npx nuxt typecheck` | `rtk npx vitest run` | `rtk npm run build` |

Biome instead of ESLint: `rtk npx biome check .`. Run the `package.json` test
script when it exists; use vitest/jest only when it is in `devDependencies`.

## Anti-slop

- `<script setup lang="ts">` consistently; no mixing Options API in new files.
- Nuxt: `useFetch` / `useAsyncData`, never `onMounted` + `fetch`.
- Respect the project's existing component and token conventions; no silent
  migration to a new pattern.
