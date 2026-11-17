// graphify auto-update — runs `graphify update .` after file edits.
// Debounced so a burst of edits produces one update, and flushed on session idle.
// No-ops when the project has no graph (graphify-out/graph.json).
//
// This is NOT a duplicate of the global graphify plugin in
// ~/.config/opencode/plugins/graphify.js. The two split the work:
//   - global  graphify.js               -> execute.before  : reminder to query
//   - project graphify-auto-update.js   -> execute.after   : regenerate the graph
// Removing this file leaves the graph stale after every edit, which is worse
// than having no graph at all. Keep both.
//
// opencode discovers every .opencode/plugins/ directory separately, and the
// global plugin's id carries its own path, so the two load without clashing.
//
// OpenCode 2.x plugin API: default-exports a definition with an id and setup(ctx).
// No opencode package is imported on purpose — a plain file in .opencode/plugins/
// cannot resolve "@opencode/plugin".
//
// IMPORTANT: keep the plugin free of backticks and $(...) in any echoed string,
// and keep graphify's own stdout quiet (stdio: "ignore") so its output never
// lands in the agent transcript.
import { existsSync } from "fs"
import { join } from "path"
import { spawn } from "child_process"

const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit", "apply_patch"])
const DEBOUNCE_MS = 1500
const UPDATE_TIMEOUT_MS = 120000
const GUARD = Symbol.for("graphify-auto-update.installed")

const runGraphify = (directory) =>
  new Promise((resolve, reject) => {
    const child = spawn("graphify", ["update", "."], {
      cwd: directory,
      stdio: "ignore",
      windowsHide: true,
      shell: process.platform === "win32",
      timeout: UPDATE_TIMEOUT_MS,
      killSignal: "SIGTERM",
    })
    child.once("error", reject)
    child.once("exit", (code, signal) => {
      if (signal) reject(new Error(`graphify update timed out after ${UPDATE_TIMEOUT_MS} ms`))
      else if (code === 0) resolve()
      else reject(new Error(`graphify update exited with code ${code}`))
    })
  })

export default {
  id: "graphify-auto-update",
  async setup(ctx) {
    if (globalThis[GUARD]) return
    globalThis[GUARD] = true

    const directory = ctx.location.directory
    const graph = join(directory, "graphify-out", "graph.json")
    const controller = new AbortController()
    let timer = null
    let running = false
    let dirty = false

    const log = (level, message, extra) => {
      // OpenCode 2 has no client.app.log on the plugin context; keep failures
      // visible but rare so they never pollute the transcript.
      try {
        console.warn(`[graphify-auto-update] ${level}: ${message}`, extra ?? "")
      } catch {
        // logging must never break the run
      }
    }

    const run = async () => {
      timer = null
      if (!existsSync(graph)) {
        dirty = false
        return
      }
      if (running) return
      running = true
      dirty = false
      try {
        await runGraphify(directory)
      } catch (err) {
        log("warn", "graphify update failed", String(err?.message ?? err))
      } finally {
        running = false
        if (dirty) schedule()
      }
    }

    const schedule = () => {
      dirty = true
      if (timer) clearTimeout(timer)
      timer = setTimeout(run, DEBOUNCE_MS)
    }

    const flush = async () => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      if (dirty && !running) await run()
    }

    await ctx.tool.hook("execute.after", (event) => {
      const tool = String(event?.tool ?? "").toLowerCase()
      if (!EDIT_TOOLS.has(tool)) return
      if (!existsSync(graph)) return
      schedule()
    })

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          if (event?.type === "session.idle") await flush()
        }
      } catch {
        // subscription aborted on unload
      }
    })()

    return () => {
      controller.abort()
      if (timer) clearTimeout(timer)
      timer = null
    }
  },
}
