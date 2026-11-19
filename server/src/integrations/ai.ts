import { env } from "../env";

/**
 * Optional, non-critical AI assist: drafts a short video description for a lesson that doesn't
 * have one, from its script text. Entirely optional — the whole production pipeline works with
 * this unconfigured; it only backs a "Suggest description" button in the lesson editor.
 */
export async function suggestVideoDescription(lessonTitle: string, scriptText: string): Promise<string> {
  if (!env.aiApiKey || !env.aiProvider) {
    throw new Error("AI_PROVIDER / AI_API_KEY are not configured.");
  }
  if (env.aiProvider !== "anthropic") {
    throw new Error(`Unsupported AI_PROVIDER: ${env.aiProvider}. Supported: "anthropic".`);
  }

  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.aiApiKey,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-haiku-5-5",
      max_tokens: 200,
      messages: [
        {
          role: "user",
          content:
            `Write a single, one-sentence video description (under 200 characters, no quotes) ` +
            `for a course lesson titled "${lessonTitle}", based on this narration script:\n\n${scriptText.slice(0, 4000)}`,
        },
      ],
    }),
  });

  if (!resp.ok) {
    throw new Error(`AI suggestion request failed (${resp.status}): ${await resp.text()}`);
  }
  const data = (await resp.json()) as { content: Array<{ type: string; text?: string }> };
  const text = data.content.find((c) => c.type === "text")?.text ?? "";
  return text.trim();
}
