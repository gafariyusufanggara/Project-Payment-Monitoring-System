# SOP — Stack Detection and Per-Stack Recommendations

Stack is never assumed. Detect it, write it down once, then load only what that
stack needs. This is the anti-hallucination step: choosing Next.js tools for a
Vue project is the most common way an agent produces unusable output.

---

## 1. Detect (fase 0, always first)

Read these files if present, in this order. Use `ctx_execute` or `rtk read`; do
not dump whole files.

| Signal | Meaning |
|---|---|
| `package.json` | JS/TS project; read `dependencies`, `devDependencies`, `scripts` |
| `pnpm-lock.yaml` / `yarn.lock` / `bun.lockb` | Package manager |
| `tsconfig.json` | TypeScript; note `strict`, path aliases |
| `next.config.*` | Next.js |
| `nuxt.config.*` | Nuxt |
| `svelte.config.js` | SvelteKit |
| `astro.config.*` | Astro |
| `vite.config.*` | Vite SPA |
| `tailwind.config.*` or `@import "tailwindcss"` in CSS | Tailwind; v3 config vs v4 `@theme` |
| `components.json` | shadcn/ui present |
| `pyproject.toml` / `requirements.txt` | Python; check `fastapi`, `django`, `flask` |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `.env.example` | Required secrets — read names only, never values |

Then write the result to `.opencode/STACK.md` in the project (create the folder
if needed). One short file, because it saves every future session the same
detection work.

### `.opencode/STACK.md` template

```markdown
# Stack

- Framework: <next|nuxt|sveltekit|astro|vite-react|vite-vue|plain-html|fastapi|django|go|rust>
- Language: <ts|js|py|go|rs>
- Package manager: <pnpm|npm|yarn|bun|pip|uv|poetry|go|cargo>
- Styling: <tailwind-v4|tailwind-v3|css-modules|styled|vanilla|none>
- Component library: <shadcn|radix|mui|antd|chakra|none>
- Design tokens: <css-vars|tailwind-theme|tokens.json|none>
- Dark mode: <class|media|none|planned>
- State/data: <react-query|zustand|pinia|redux|trpc|none>
- Test: <vitest|jest|playwright|pytest|go test|cargo test|none>
- Lint/format: <eslint|biome|ruff|golangci-lint|clippy>
- Typecheck: <tsc|vue-tsc|svelte-check|mypy|null>
- Build: <command>
- Dev server: <command> on <port>
```

Bootstrap detection in one shot. Commands run from the session cwd — use
absolute paths, or `cd <project-root>` first. Scope every `rtk find` to a top
level folder so `node_modules` does not flood the output:

```js
ctx_batch_execute(commands: [
  {label:"manifest-js", command:"rtk json package.json"},
  {label:"manifest-py", command:"rtk find . -maxdepth 2 -name pyproject.toml"},
  {label:"manifest-go", command:"rtk find . -maxdepth 2 -name go.mod"},
  {label:"manifest-rs", command:"rtk find . -maxdepth 2 -name Cargo.toml"},
  {label:"configs",     command:"rtk find . -maxdepth 2 -name *.config.*"},
  {label:"locks",       command:"rtk find . -maxdepth 1 -name *lock*"}
], queries: ["framework","package manager","styling","test runner"])
```

Command rules that make the batch survive on Windows (all verified):

- No quotes around globs: `-name *.config.*`, never `-name '*.config.*'`.
- No `-not` / `-exec` / compound action predicates; rtk rejects them.
- `rtk json` only reads JSON. For TOML/YAML/other, use `rtk read`.
- `locks` stays at `-maxdepth 1`. At depth 2 it can match
  `node_modules/.package-lock.json`.

## 2. Load only this stack's rules

| Stack | MCP to use | Skills to load |
|---|---|---|
| Next.js / React | `playwright`, `chrome-devtools`, `shadcn` (only if `components.json` exists) | `hallmark`, `refactoring-ui`, `design-taste`, `frontend-design` |
| Vue / Nuxt | `playwright`, `chrome-devtools` | `hallmark`, `refactoring-ui`, `design-taste` |
| Svelte / SvelteKit | `playwright`, `chrome-devtools` | `hallmark`, `refactoring-ui`, `design-taste` |
| Astro | `playwright`, `chrome-devtools` | `hallmark`, `refactoring-ui`, `design-taste` |
| Vite SPA (React/Vue) | `playwright`, `chrome-devtools` | `hallmark`, `refactoring-ui`, `design-taste` |
| Plain HTML/CSS | none | `hallmark`, `refactoring-ui`, `design-taste` |
| FastAPI / Django / Flask | none | `design-patterns`, `code-quality` |
| Go | none | `design-patterns`, `code-quality` |
| Rust | none | `design-patterns`, `code-quality` |

There is no documentation MCP installed. Library documentation is fetched on
demand, per `.opencode/sops/CONTEXT.md` § 3b:

```
ctx_fetch_and_index(<official docs URL>, source: "docs-<lib>")
ctx_search(queries: [...], source: "docs-<lib>")
```

URL unknown -> `tavily_tavily_search`, then fetch the official result. Never
write a third-party API call that was not verified in this session.

Project documents beat upstream docs:

| Source | Authority |
|---|---|
| `docs/` (PRD, STACK, features, DESIGN, ADR) | Highest — intent and decisions |
| The existing code | High — real conventions |
| Official library docs | Medium — how the API works at that version |
| Model memory | Lowest — verify before use |

## 3. Commands per stack (verify phase)

Run these with `rtk` prefix. Missing scripts are not an error — skip and say so.

| Stack | Lint | Typecheck | Test | Build |
|---|---|---|---|---|
| Next.js (eslint) | `rtk npx eslint .` | `rtk npx tsc --noEmit` | `rtk npx vitest run` | `rtk npm run build` |
| Nuxt | `rtk npx eslint .` | `rtk npx nuxt typecheck` | `rtk npx vitest run` | `rtk npm run build` |
| SvelteKit | `rtk npx eslint .` | `rtk npx svelte-check` | `rtk npx vitest run` | `rtk npm run build` |
| Astro | `rtk npx eslint .` | `rtk npx astro check` | `rtk npx vitest run` | `rtk npm run build` |
| Vite SPA | `rtk npx eslint .` | `rtk npx tsc --noEmit` | `rtk npx vitest run` | `rtk npm run build` |
| Python | `rtk ruff check` | `rtk mypy .` | `rtk pytest` | `rtk python -m build` |
| Go | `rtk go vet ./...` | (built in) | `rtk go test ./...` | `rtk go build ./...` |
| Rust | `rtk cargo clippy` | (built in) | `rtk cargo test` | `rtk cargo build` |

If Biome is present instead of ESLint, substitute `rtk npx biome check .`.

The Test column is a default, not a fact. Run the `test` script from `package.json` when it exists. Use `vitest` only when it is in `devDependencies`; `jest` only when it is. Never assume the runner.

## 4. Stack-specific anti-slop notes

### Next.js / React
- Server Components by default; `"use client"` only where there is real
  interaction or browser API use.
- Data fetching in a Server Component or Route Handler, not `useEffect`.
- Never ship `<img>`; use `next/image` with explicit `width`/`height` or
  `fill` + sized parent.
- Font loading via `next/font`, never a raw `<link>` to Google Fonts.

### Vue / Nuxt
- `<script setup lang="ts">` consistently; no mixing Options API in new files.
- Nuxt: `useFetch` / `useAsyncData`, never `onMounted` + `fetch`.

### Svelte / SvelteKit
- Svelte 5 runes (`$state`, `$derived`, `$effect`); do not mix with legacy
  `export let` in the same component.
- Load in `+page.server.ts` / `+layout.server.ts`.

### Astro
- Zero JS by default. `client:load` only when hydration is proven necessary.
- Islands over a page-wide SPA.

### shadcn/ui
- Components are owned source, not a dependency. Edit them in place.
- Never restyle with `!important`; change the token.
- If a shadcn MCP server is configured, query it before writing a component by hand. If not configured, read the existing components in the repo and state that the MCP was unavailable.

## 5. When no stack is detected

Say so explicitly and stop:

> No `package.json`, `pyproject.toml`, `go.mod`, or `Cargo.toml` found in
> `<path>`. Nothing to detect. Two options: (a) point me at the project root,
> or (b) tell me the stack and I will scaffold it.

Do not guess a stack and start writing files. That is the failure mode this SOP
exists to prevent.
