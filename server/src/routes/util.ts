import type { NextFunction, Request, RequestHandler, Response } from "express";

/** Wrap an async Express handler so a rejected promise is forwarded to next() instead of
 * crashing the process (Express 4 doesn't do this automatically for async handlers). */
export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<unknown>
): RequestHandler {
  return (req, res, next) => {
    fn(req, res, next).catch(next);
  };
}

export function notFound(res: Response, message = "Not found."): void {
  res.status(404).json({ error: message });
}

export function badRequest(res: Response, message: string): void {
  res.status(400).json({ error: message });
}
