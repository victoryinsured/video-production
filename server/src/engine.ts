import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { env } from "./env";
import { newJobFilePath } from "./paths";

export class EngineError extends Error {
  constructor(message: string, readonly traceback?: string) {
    super(message);
    this.name = "EngineError";
  }
}

/**
 * Invoke the Python engine's CLI as a short-lived subprocess for a single pipeline step. Writes
 * `job` to a temp JSON file, runs `python -m victory_engine.cli <file>`, parses the single JSON
 * object printed to stdout, and deletes the temp file. The engine is never a long-running
 * service — one process per step, per the architecture decision in ARCHITECTURE.md §3.
 */
export async function runEngineStep<T = Record<string, unknown>>(job: Record<string, unknown>): Promise<T> {
  const jobPath = newJobFilePath();
  await fs.writeFile(jobPath, JSON.stringify(job), "utf-8");

  try {
    const { stdout, stderr, code } = await runPython(["-m", "victory_engine.cli", jobPath]);

    let parsed: unknown;
    try {
      parsed = JSON.parse(stdout.trim());
    } catch {
      throw new EngineError(
        `Engine step "${job.step}" produced non-JSON output (exit code ${code}): ${stdout || stderr}`.slice(0, 4000)
      );
    }

    if (parsed && typeof parsed === "object" && "error" in (parsed as Record<string, unknown>)) {
      const errObj = parsed as { error: string; traceback?: string };
      throw new EngineError(`Engine step "${job.step}" failed: ${errObj.error}`, errObj.traceback);
    }

    if (code !== 0) {
      throw new EngineError(`Engine step "${job.step}" exited with code ${code}: ${stderr.slice(0, 2000)}`);
    }

    return parsed as T;
  } finally {
    await fs.unlink(jobPath).catch(() => undefined);
  }
}

function pythonBinary(): string {
  const venvBin = path.join(path.resolve(env.engineDir), ".venv", "bin", "python3");
  return venvBin;
}

async function runPython(args: string[]): Promise<{ stdout: string; stderr: string; code: number }> {
  const engineDir = path.resolve(env.engineDir);
  const venvPython = pythonBinary();
  const hasVenv = await fs
    .access(venvPython)
    .then(() => true)
    .catch(() => false);
  const bin = hasVenv ? venvPython : env.pythonBin;

  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { cwd: engineDir });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => reject(err));
    child.on("close", (code) => resolve({ stdout, stderr, code: code ?? 1 }));
  });
}
