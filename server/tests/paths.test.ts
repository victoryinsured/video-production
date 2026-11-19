import { describe, expect, it } from "vitest";
import { sanitizeFilename } from "../src/paths";

describe("sanitizeFilename", () => {
  it("strips directory traversal sequences", () => {
    expect(sanitizeFilename("../../../etc/passwd")).toBe("passwd");
  });

  it("strips absolute paths down to a basename", () => {
    expect(sanitizeFilename("/etc/shadow")).toBe("shadow");
    expect(sanitizeFilename("C:\\Windows\\System32\\evil.dll")).not.toContain("\\");
  });

  it("replaces unsafe characters", () => {
    expect(sanitizeFilename("my file!@#$.pdf")).toBe("my_file_.pdf");
  });

  it("strips leading dots so a hidden-file / parent-dir trick can't sneak through", () => {
    expect(sanitizeFilename("..hidden")).toBe("hidden");
    expect(sanitizeFilename("...")).toBe("file");
  });

  it("falls back to a safe default for empty input", () => {
    expect(sanitizeFilename("")).toBe("file");
    expect(sanitizeFilename("   ")).toBe("file");
  });

  it("preserves ordinary filenames unchanged", () => {
    expect(sanitizeFilename("cheat_sheet-v2.pdf")).toBe("cheat_sheet-v2.pdf");
  });

  it("truncates extremely long filenames", () => {
    const long = "a".repeat(500) + ".pdf";
    expect(sanitizeFilename(long).length).toBeLessThanOrEqual(200);
  });
});
