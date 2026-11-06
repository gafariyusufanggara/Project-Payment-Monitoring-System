---
description: "Build or redesign a page with the Hallmark anti-slop skill: pick a design direction, build the hero first, lint in a real browser, then expand. Use for new pages, landing pages, redesigns, and any UI that must not look AI-generated."
agent: ui-designer
subtask: false
---

Load `.opencode/skills/hallmark/SKILL.md` and follow its Flow. This command pins the
project-specific parts of that flow.

## Arguments

- `<prompt>` — build something new.
- `redesign <path>` — full redesign keeping content and wiring.
- `audit <path>` — report only (`/ui-audit` is the richer version).

Hallmark never touches an existing design unless the user names it. If the user
asked for a new feature in an existing app, use the app's own system instead and
say so.

## Flow pinning

0. Pre-flight: read the project (`.opencode/sops/STACKS.md` detection). Note any locked
   `DESIGN.md` at the root — it overrides Hallmark themes.
1. Ask once: material, audience, use, tone. Never invent material.
2. Shape the page, then name it.
3. Deal a theme (`node .opencode/skills/hallmark/scripts/theme.mjs deal`), or design
   freely when the user asks for custom.
4. Load only: the chosen theme file, `references/gates.md` 1-4, plus
   layout / imagery / craft / genre as needed.
5. Build the hero alone. Render it. Review it cold. Then the rest of the page.
6. Sweep:

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <output> --render
```

Fix every FAIL. Fix or waive every REFLEX with real evidence in the CSS stamp.

## Verification beyond sloplint

- Screenshots at 320 / 768 / 1280 / 1440 via `playwright` MCP.
- `chrome-devtools` MCP against the production/preview server: console, network,
  a11y critical, LCP, CLS.
- Keyboard pass: Tab reaches every control, focus visible.
- Reduced motion: animations degrade to instant.
- Empty / loading / error states exist.
- Dark mode implemented or declared out of scope.

## Output

```
Direction: <one sentence>
Files: <paths>
sloplint: <exit code, counts>
Screenshots: <paths>
Waivers: <gate + evidence + reason, or none>
Not done: <what and why>
Next: <one action>
```

Never describe the design in adjectives. Show the evidence.
