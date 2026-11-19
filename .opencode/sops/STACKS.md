# SOP — Stack Detection (index)

Stack is never assumed. Detect it, write it down once, then load **one** stack
file. Choosing Next.js tools for a Vue project is the most common way to produce
unusable output.

## Read map

| Task | Read |
|---|---|
| Detect stack, write `.opencode/STACK.md` | §1, then `stacks/_template.md` |
| Pick stack file, MCP, skills | §2 |
| Verify commands for this stack | the stack file's **Verify** section |
| No manifest found | §3 |

## 1. Detect (phase 0b, always first)

Read these signals with `ctx_execute` / `rtk read`; never dump whole files.

| Signal | Meaning |
|---|---|
| `package.json` | JS/TS; read deps, devDeps, scripts |
| lockfile (`pnpm-lock`, `yarn.lock`, `bun.lockb`) | package manager |
| `next/nuxt/svelte/astro/vite.config.*` | framework |
| `tsconfig.json` | TypeScript, `strict`, aliases |
| `tailwind.config.*` or `@import "tailwindcss"` | Tailwind v3 vs v4 `@theme` |
| `components.json` | shadcn/ui present |
| `pyproject.toml` / `requirements.txt` | Python: fastapi / django / flask |
| `go.mod` / `Cargo.toml` | Go / Rust |
| `.env.example` | secret names only, never values |

One batch, cwd-scoped. Use absolute paths or `cd <project-root>` first.
`commands` is a list of raw shell strings; `queries` are FTS keywords that must
appear in that output:

```js
ctx_batch(commands: [
  "rtk json package.json",
  "rtk find . -maxdepth 2 -name pyproject.toml",
  "rtk find . -maxdepth 2 -name go.mod",
  "rtk find . -maxdepth 2 -name Cargo.toml",
  "rtk find . -maxdepth 2 -name *.config.*",
  "rtk find . -maxdepth 1 -name *lock*"
], queries: ["version","dependencies","script","name","private"])
```

Windows rules: no quotes around globs, no `-not` / `-exec`, `rtk json` for JSON
only, `locks` stays at `-maxdepth 1`. A command that fails or prints
`0 for <pattern>` is information, not an error.

### `.opencode/STACK.md`

Write it once per project from `stacks/_template.md`. If `docs/STACK.md` exists it
is authoritative; `.opencode/STACK.md` records what the code actually contains.
Report differences; never overwrite either silently.

## 2. Load one stack file

| Detected | Load | Browser / MCP | Skills |
|---|---|---|---|
| Next.js / React | `stacks/nextjs.md` | `playwright-cli` CLI; chrome-devtools MCP; shadcn if `components.json` | hallmark, refactoring-ui, design-taste |
| Vue / Nuxt | `stacks/vue.md` | `playwright-cli` CLI; chrome-devtools MCP | hallmark, refactoring-ui, design-taste |
| Svelte / SvelteKit | `stacks/svelte.md` | `playwright-cli` CLI; chrome-devtools MCP | hallmark, refactoring-ui, design-taste |
| Astro | `stacks/astro.md` | `playwright-cli` CLI; chrome-devtools MCP | hallmark, refactoring-ui, design-taste |
| Vite SPA | `stacks/vite.md` | `playwright-cli` CLI; chrome-devtools MCP | hallmark, refactoring-ui, design-taste |
| Plain HTML/CSS | this file + a framework row for design skills | `playwright-cli` CLI; chrome-devtools MCP | hallmark, refactoring-ui, design-taste |
| FastAPI / Django / Flask | `stacks/python.md` | none | backend rules live in the stack file |
| Go | `stacks/go.md` | none | backend rules live in the stack file |
| Rust | `stacks/rust.md` | none | backend rules live in the stack file |

No dedicated documentation server is required. Fetch library docs on demand via
`.opencode/sops/CONTEXT.md` → **External library documentation** (whichever
search or fetch tool is enabled).

## 3. No stack detected

Say so and stop:

> No `package.json`, `pyproject.toml`, `go.mod`, or `Cargo.toml` found in
> `<path>`. Nothing to detect. Point me at the project root, or tell me the stack
> and I will scaffold it.

Do not guess a stack and start writing files.
