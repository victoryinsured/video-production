import { env } from "../env";

export interface ElevenLabsVoice {
  voiceId: string;
  name: string;
  category?: string;
}

async function request(path: string): Promise<Response> {
  if (!env.elevenLabsApiKey) {
    throw new Error("ELEVENLABS_API_KEY is not configured.");
  }
  return fetch(`https://api.elevenlabs.io/v1${path}`, {
    headers: { "xi-api-key": env.elevenLabsApiKey },
  });
}

export async function listVoices(): Promise<ElevenLabsVoice[]> {
  const resp = await request("/voices");
  if (!resp.ok) {
    throw new Error(`ElevenLabs list-voices failed (${resp.status}): ${await resp.text()}`);
  }
  const data = (await resp.json()) as { voices: Array<{ voice_id: string; name: string; category?: string }> };
  return data.voices.map((v) => ({ voiceId: v.voice_id, name: v.name, category: v.category }));
}

/** Diagnostics "Test Connection": proves the API key is valid by listing voices. */
export async function testElevenLabsConnection(): Promise<{ ok: boolean; message: string }> {
  try {
    const voices = await listVoices();
    return { ok: true, message: `Connected. ${voices.length} voice(s) available.` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}
