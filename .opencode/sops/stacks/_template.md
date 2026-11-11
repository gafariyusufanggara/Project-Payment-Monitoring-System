# `.opencode/STACK.md` template

Copy this into `.opencode/STACK.md` and fill it. One short file per project.

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

If `docs/STACK.md` exists it is authoritative; `.opencode/STACK.md` records what
the code actually contains. Report differences; never overwrite either silently.
