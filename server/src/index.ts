import path from "node:path";
import express from "express";
import cookieSession from "cookie-session";
import { env } from "./env";
import { requireAuth } from "./auth";
import { authRouter } from "./routes/auth";
import { coursesRouter } from "./routes/courses";
import { modulesRouter } from "./routes/modules";
import { lessonsRouter } from "./routes/lessons";
import { documentsRouter } from "./routes/documents";
import { brandRouter } from "./routes/brand";
import { voicesRouter } from "./routes/voices";
import { jobsRouter } from "./routes/jobs";
import { dashboardRouter } from "./routes/dashboard";
import { diagnosticsRouter } from "./routes/diagnostics";

const app = express();

// No CORS middleware: the production app is served same-origin (this Express app serves the
// built web/ static files directly), and in development the Vite dev server proxies /api to
// this same port — see web/vite.config.ts. There is never a cross-origin request to allow.
app.use(express.json({ limit: "2mb" }));
app.use(
  cookieSession({
    name: "victory_session",
    secret: env.sessionSecret,
    maxAge: 7 * 24 * 60 * 60 * 1000,
    sameSite: "lax",
  })
);

app.use("/api/auth", authRouter);

app.use("/api/courses", requireAuth, coursesRouter);
app.use("/api/modules", requireAuth, modulesRouter);
app.use("/api/lessons", requireAuth, lessonsRouter);
app.use("/api/documents", requireAuth, documentsRouter);
app.use("/api/brand-templates", requireAuth, brandRouter);
app.use("/api/voices", requireAuth, voicesRouter);
app.use("/api/jobs", requireAuth, jobsRouter);
app.use("/api/dashboard", requireAuth, dashboardRouter);
app.use("/api/diagnostics", requireAuth, diagnosticsRouter);

if (env.nodeEnv === "production") {
  const webDist = path.join(__dirname, "..", "..", "web", "dist");
  app.use(express.static(webDist));
  app.get("*", (_req, res) => {
    res.sendFile(path.join(webDist, "index.html"));
  });
}

// Error handler must be registered last: Express only routes a next(err) call to error
// middleware declared after the point where it was thrown/called.
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err);
  res.status(500).json({ error: err.message ?? "Internal server error." });
});

app.listen(env.port, () => {
  console.log(`Victory Video Studio API listening on port ${env.port} (${env.nodeEnv}).`);
});
