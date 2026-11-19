/** Mirrors engine/victory_engine/text_utils.py::slugify so a course parsed by the Python engine
 * and looked up by slug on the Node side always produce the same identifier. */
export function slugify(text: string): string {
  let result = text.replace(/—/g, "-").replace(/–/g, "-").replace(/['’]/g, "");
  result = result
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  result = result.replace(/_+/g, "_");
  result = result.slice(0, 110).replace(/^_+|_+$/g, "");
  return result || "lesson";
}
