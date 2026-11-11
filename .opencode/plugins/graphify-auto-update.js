// graphify auto-update — runs `graphify update .` after file edits.
// Debounced so a burst of edits produces one update, and flushed on session idle.
// No-ops when the project has no graph (graphify-out/graph.json).
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

export const GraphifyAutoUpdate = async ({ $, directory, client }) => {
  if (globalThis[GUARD]) return {}
  globalThis[GUARD] = true

  const graph = join(directory, "graphify-out", "graph.json")
  let timer = null
  let running = false
  let dirty = false

  const log = async (level, message, extra) => {
    try {
      await client?.app?.log?.({ body: { service: "graphify-auto-update", level, message, extra } })
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
      await log("warn", "graphify update failed", { error: String(err?.message ?? err) })
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

  return {
    "tool.execute.after": async (input) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (!EDIT_TOOLS.has(tool)) return
      if (!existsSync(graph)) return
      schedule()
    },
    event: async ({ event }) => {
      if (event?.type === "session.idle") await flush()
    },
  }
}
