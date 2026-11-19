import { Router } from "express";
import { authIsEnabled, checkPassword } from "../auth";
import { asyncHandler, badRequest } from "./util";

export const authRouter = Router();

authRouter.get("/status", (req, res) => {
  const session = (req as unknown as { session?: { authenticated?: boolean } }).session;
  res.json({ authEnabled: authIsEnabled(), authenticated: authIsEnabled() ? Boolean(session?.authenticated) : true });
});

authRouter.post(
  "/login",
  asyncHandler(async (req, res) => {
    const { password } = req.body as { password?: string };
    if (!password) return badRequest(res, "Password is required.");
    if (!checkPassword(password)) {
      res.status(401).json({ error: "Incorrect password." });
      return;
    }
    const session = (req as unknown as { session?: { authenticated?: boolean } }).session;
    if (session) session.authenticated = true;
    res.json({ ok: true });
  })
);

authRouter.post("/logout", (req, res) => {
  const session = (req as unknown as { session?: { authenticated?: boolean } | null }).session;
  if (session) (req as unknown as { session: null }).session = null;
  res.json({ ok: true });
});
