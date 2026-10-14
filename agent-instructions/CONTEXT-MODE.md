# Context Mode Policy

Use when Context Mode MCP is available.

## Core Principle
Protect the context window from raw-output flooding.

Analyze, count, filter, compare, parse, or transform data in the sandbox and return
only the derived answer.

## Routing
Prefer:
1. `context-mode_ctx_batch_execute` for 3+ related commands/gathering
2. `context-mode_ctx_execute` for programmatic analysis
3. `context-mode_ctx_execute_file` for file analysis without flooding context
4. `context-mode_ctx_search` for targeted follow-up queries
5. `context-mode_ctx_fetch_and_index` for web fetching before search
6. `context-mode_ctx_index` for reusable indexed content

Use `Read` when exact file bytes are required for editing.

## Large Output
If raw output could exceed roughly 20 lines, process/filter it in the sandbox and
emit only the useful result.

## Network
Follow the configured Context Mode fetch/index workflow instead of blocked direct
curl/wget/HTTP routes. Batch independent I/O when supported; avoid parallelizing
stateful writes or CPU-heavy commands.

## File Analysis
For analysis/exploration, prefer sandbox processing. For editing, read only the
exact file/range required by the editor.

## Session Continuity
When resuming work, search persisted project/session context before asking the user
to repeat recorded decisions or constraints.

Do not call maintenance commands such as stats/doctor/upgrade/purge without a reason.
