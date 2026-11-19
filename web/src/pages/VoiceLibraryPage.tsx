import { useEffect, useState } from "react";
import { api, ApiError, Voice } from "../api";

interface AvailableVoice {
  voiceId: string;
  name: string;
  category?: string;
}

export default function VoiceLibraryPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [available, setAvailable] = useState<AvailableVoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [manualName, setManualName] = useState("");
  const [manualId, setManualId] = useState("");

  useEffect(() => {
    load();
    loadAvailable();
  }, []);

  async function load() {
    try {
      const resp = await api.get<{ voices: Voice[] }>("/voices");
      setVoices(resp.voices);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load voice library.");
    }
  }

  async function loadAvailable() {
    try {
      const resp = await api.get<{ voices: AvailableVoice[] }>("/voices/available");
      setAvailable(resp.voices);
    } catch {
      // ElevenLabs may not be configured yet — the manual-entry form below still works.
    }
  }

  async function addFromAvailable(voice: AvailableVoice) {
    try {
      await api.post("/voices", { name: voice.name, elevenLabsVoiceId: voice.voiceId });
      setNotice(`Added "${voice.name}" to the library.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add voice.");
    }
  }

  async function addManual() {
    if (!manualName.trim() || !manualId.trim()) return;
    try {
      await api.post("/voices", { name: manualName.trim(), elevenLabsVoiceId: manualId.trim() });
      setManualName("");
      setManualId("");
      setNotice("Voice added.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add voice.");
    }
  }

  async function setDefault(id: string) {
    try {
      await api.patch(`/voices/${id}`, { isDefault: true });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not set default.");
    }
  }

  async function remove(id: string) {
    try {
      await api.delete(`/voices/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete voice.");
    }
  }

  const libraryIds = new Set(voices.map((v) => v.elevenLabsVoiceId));

  return (
    <div>
      <h1>Voice Library</h1>
      <p className="page-subtitle">Credentials stay server-side — only voice names and IDs live here.</p>
      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="success-banner">{notice}</div>}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Your library</h2>
        {voices.length === 0 && <p>No voices added yet.</p>}
        {voices.map((voice) => (
          <div className="card-row" key={voice.id} style={{ padding: "8px 0" }}>
            <div>
              <strong>{voice.name}</strong> {voice.isDefault && <span className="badge status-complete">default</span>}
              <p className="page-subtitle" style={{ margin: "2px 0 0" }}>{voice.elevenLabsVoiceId}</p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {!voice.isDefault && (
                <button className="secondary" onClick={() => setDefault(voice.id)}>
                  Make default
                </button>
              )}
              <button className="danger" onClick={() => remove(voice.id)}>
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {available.length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Available in your ElevenLabs account</h2>
          {available.map((voice) => (
            <div className="card-row" key={voice.voiceId} style={{ padding: "6px 0" }}>
              <div>
                {voice.name} <span className="page-subtitle">({voice.category ?? "voice"})</span>
              </div>
              <button className="secondary" disabled={libraryIds.has(voice.voiceId)} onClick={() => addFromAvailable(voice)}>
                {libraryIds.has(voice.voiceId) ? "Added" : "Add"}
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Add manually</h2>
        <p className="page-subtitle">Use this if ElevenLabs isn't configured yet, or you want to paste a voice ID directly.</p>
        <div className="field-row">
          <div className="field">
            <label>Name</label>
            <input type="text" value={manualName} onChange={(e) => setManualName(e.target.value)} />
          </div>
          <div className="field">
            <label>ElevenLabs Voice ID</label>
            <input type="text" value={manualId} onChange={(e) => setManualId(e.target.value)} />
          </div>
        </div>
        <button className="secondary" onClick={addManual}>
          Add voice
        </button>
      </div>
    </div>
  );
}
