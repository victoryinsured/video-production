import { prisma } from "../db";
import { executeStep } from "./handlers";
import { isStepRunnable } from "./pipeline";

const POLL_INTERVAL_MS = Number(process.env.WORKER_POLL_INTERVAL_MS ?? "2000");
const MAX_ATTEMPTS = Number(process.env.WORKER_MAX_ATTEMPTS ?? "3");

let shuttingDown = false;

async function claimNextStep() {
  const candidates = await prisma.jobStep.findMany({
    where: { status: "pending" },
    orderBy: { createdAt: "asc" },
    take: 25,
  });

  for (const step of candidates) {
    if (!(await isStepRunnable(step.lessonId, step.step, step.resourceId))) continue;

    // Optimistic claim: only succeeds if another worker process hasn't already picked it up.
    const claimed = await prisma.jobStep.updateMany({
      where: { id: step.id, status: "pending" },
      data: { status: "running", startedAt: new Date() },
    });
    if (claimed.count === 1) {
      return step;
    }
  }
  return null;
}

async function runOnce(): Promise<boolean> {
  const step = await claimNextStep();
  if (!step) return false;

  if (!step.resourceId) {
    await prisma.lesson.update({ where: { id: step.lessonId }, data: { status: "producing" } }).catch(() => undefined);
  }

  try {
    const result = await executeStep(step);
    await prisma.jobStep.update({
      where: { id: step.id },
      data: {
        status: "complete",
        resultJson: JSON.stringify(result),
        completedAt: new Date(),
        error: null,
        attempts: { increment: 1 },
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const attempts = step.attempts + 1;
    await prisma.jobStep.update({
      where: { id: step.id },
      data: {
        status: attempts >= MAX_ATTEMPTS ? "failed" : "pending",
        error: message,
        attempts,
      },
    });
    if (attempts >= MAX_ATTEMPTS && !step.resourceId) {
      await prisma.lesson.update({ where: { id: step.lessonId }, data: { status: "failed" } }).catch(() => undefined);
    }
    console.error(`[worker] step ${step.step} (lesson ${step.lessonId}) failed: ${message}`);
  }

  return true;
}

/**
 * A step left "running" when a previous worker process was killed (deploy restart, crash,
 * OOM-kill) is not actually in flight anymore — nothing is still executing it — so it would
 * otherwise sit stuck forever (the claim query in claimNextStep only ever looks at "pending"
 * rows). Reset any such orphaned rows back to "pending" once, at startup, before polling begins.
 */
async function recoverOrphanedSteps(): Promise<void> {
  const result = await prisma.jobStep.updateMany({
    where: { status: "running" },
    data: { status: "pending" },
  });
  if (result.count > 0) {
    console.log(`[worker] recovered ${result.count} step(s) left "running" by a previous process.`);
  }
}

export async function loop() {
  console.log("[worker] Victory Video Studio job-queue worker started.");
  await recoverOrphanedSteps();
  while (!shuttingDown) {
    let didWork = false;
    try {
      didWork = await runOnce();
    } catch (err) {
      console.error("[worker] unexpected error in poll loop:", err);
    }
    if (!didWork) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }
}

process.on("SIGTERM", () => {
  shuttingDown = true;
});
process.on("SIGINT", () => {
  shuttingDown = true;
});

if (require.main === module) {
  loop().catch((err) => {
    console.error("[worker] fatal error:", err);
    process.exit(1);
  });
}
