import type { NextFunction, Request, Response } from "express";
import { env } from "./env";

// cookie-session's own ambient types (@types/cookie-session) already augment
// express.Request.session with a CookieSessionObject; we only need a narrower view of the one
// field this module reads and writes.
interface SessionRequest extends Request {
  session?: ({ authenticated?: boolean } & Record<string, unknown>) | null;
}

/**
 * Gate every non-public route behind a single shared admin password (cookie-session, no
 * database-backed accounts needed for a single-operator deployment). If ADMIN_PASSWORD is unset,
 * auth is a no-op — convenient for local development, documented as a requirement in DEPLOYMENT.md
 * before exposing a deployment to the internet.
 */
export function requireAuth(req: SessionRequest, res: Response, next: NextFunction): void {
  if (!env.adminPassword) {
    next();
    return;
  }
  if (req.session?.authenticated) {
    next();
    return;
  }
  res.status(401).json({ error: "Not authenticated." });
}

export function checkPassword(password: string): boolean {
  if (!env.adminPassword) return true;
  return password === env.adminPassword;
}

export function authIsEnabled(): boolean {
  return Boolean(env.adminPassword);
}
