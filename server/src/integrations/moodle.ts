import { env } from "../env";

function requireConfig(): { baseUrl: string; token: string } {
  if (!env.moodleBaseUrl || !env.moodleToken) {
    throw new Error("MOODLE_BASE_URL / MOODLE_TOKEN are not configured.");
  }
  return { baseUrl: env.moodleBaseUrl.replace(/\/$/, ""), token: env.moodleToken };
}

async function callFunction<T>(wsfunction: string, params: Record<string, string | number>): Promise<T> {
  const { baseUrl, token } = requireConfig();
  const url = new URL(`${baseUrl}/webservice/rest/server.php`);
  url.searchParams.set("wstoken", token);
  url.searchParams.set("wsfunction", wsfunction);
  url.searchParams.set("moodlewsrestformat", "json");
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, String(value));
  }
  const resp = await fetch(url.toString(), { method: "POST" });
  const data = (await resp.json()) as unknown;
  if (data && typeof data === "object" && "exception" in (data as Record<string, unknown>)) {
    const err = data as { exception: string; message: string };
    throw new Error(`Moodle ${wsfunction} failed: ${err.message} (${err.exception})`);
  }
  return data as T;
}

export interface MoodleSiteInfo {
  sitename: string;
  username: string;
  functions: Array<{ name: string }>;
}

export async function getSiteInfo(): Promise<MoodleSiteInfo> {
  return callFunction<MoodleSiteInfo>("core_webservice_get_site_info", {});
}

export async function createOrUpdateSection(courseId: number, sectionName: string): Promise<number> {
  const result = await callFunction<Array<{ id: number }>>("core_course_edit_section", {
    courseid: courseId,
    name: sectionName,
  } as Record<string, string | number>);
  return result[0]?.id ?? 0;
}

export async function publishUrlActivity(
  courseId: number,
  sectionId: number,
  name: string,
  intro: string,
  externalUrl: string
): Promise<number> {
  const result = await callFunction<{ cmid: number }>("core_course_edit_module", {
    action: "add",
    courseid: courseId,
    sectionid: sectionId,
    modulename: "url",
    name,
    intro,
    externalurl: externalUrl,
  } as Record<string, string | number>);
  return result.cmid;
}

/**
 * Diagnostics "Test Connection": `core_webservice_get_site_info` proves the token itself is
 * valid, but a token can be valid while still lacking the specific `core_course_edit_module`
 * permission this app needs to actually publish lessons — so this also checks the token's
 * function list for that permission and reports it as a (non-fatal) warning rather than a pass.
 */
export async function testMoodleConnection(): Promise<{ ok: boolean; message: string }> {
  try {
    const info = await getSiteInfo();
    const hasEditModule = info.functions.some((f) => f.name === "core_course_edit_module");
    if (!hasEditModule) {
      return {
        ok: false,
        message: `Connected as "${info.username}" on "${info.sitename}", but this token's role is missing the core_course_edit_module function needed to publish lessons.`,
      };
    }
    return { ok: true, message: `Connected as "${info.username}" on "${info.sitename}".` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}
