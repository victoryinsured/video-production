import { useEffect, useRef, useState } from "react";
import { api, ApiError, BrandTemplate } from "../api";

interface ColorField {
  key: string;
  label: string;
}

const COLOR_FIELDS: ColorField[] = [
  { key: "ink", label: "Ink" },
  { key: "maroon_black", label: "Maroon Black" },
  { key: "maroon_deep", label: "Maroon Deep" },
  { key: "maroon", label: "Maroon" },
  { key: "cream", label: "Cream" },
  { key: "parchment", label: "Parchment" },
  { key: "gold", label: "Gold" },
  { key: "gold_dark", label: "Gold Dark" },
];

function rgbToHex([r, g, b]: number[]): string {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

function hexToRgb(hex: string): number[] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export default function BrandEditorPage() {
  const [templates, setTemplates] = useState<BrandTemplate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const logoInput = useRef<HTMLInputElement>(null);
  const introInput = useRef<HTMLInputElement>(null);
  const outroInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const resp = await api.get<{ templates: BrandTemplate[] }>("/brand-templates");
      setTemplates(resp.templates);
      if (!selectedId && resp.templates.length > 0) setSelectedId(resp.templates[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load brand templates.");
    }
  }

  async function createTemplate() {
    try {
      const resp = await api.post<{ template: BrandTemplate }>("/brand-templates", {
        name: "New Brand Template",
        colors: {},
        fonts: {},
        cover: {},
      });
      await load();
      setSelectedId(resp.template.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create template.");
    }
  }

  async function deleteTemplate(id: string) {
    try {
      await api.delete(`/brand-templates/${id}`);
      setSelectedId(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete template.");
    }
  }

  const selected = templates.find((t) => t.id === selectedId) ?? null;

  async function patch(id: string, data: Record<string, unknown>) {
    try {
      await api.patch(`/brand-templates/${id}`, data);
      setNotice("Saved.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    }
  }

  async function uploadAsset(id: string, field: "logo" | "intro" | "outro", file: File) {
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload(`/brand-templates/${id}/assets/${field}`, form);
      setNotice(`${field} uploaded.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  return (
    <div>
      <h1>Brand Editor</h1>
      <p className="page-subtitle">Manage brand templates: colors, fonts, logo, intro/outro, captions.</p>
      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="success-banner">{notice}</div>}

      <div className="card-row" style={{ marginBottom: 16 }}>
        <select value={selectedId ?? ""} onChange={(e) => setSelectedId(e.target.value)} style={{ maxWidth: 320 }}>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
              {t.isDefault ? " (default)" : ""}
            </option>
          ))}
        </select>
        <button className="secondary" onClick={createTemplate}>
          + New template
        </button>
      </div>

      {selected && (
        <div className="card">
          <div className="field-row">
            <div className="field">
              <label>Name</label>
              <input
                type="text"
                defaultValue={selected.name}
                onBlur={(e) => patch(selected.id, { name: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Default template</label>
              <select
                value={selected.isDefault ? "yes" : "no"}
                onChange={(e) => patch(selected.id, { isDefault: e.target.value === "yes" })}
              >
                <option value="no">No</option>
                <option value="yes">Yes — use for new courses</option>
              </select>
            </div>
          </div>

          <h2>Colors</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {COLOR_FIELDS.map((field) => {
              const colors = JSON.parse(selected.colors || "{}") as Record<string, number[]>;
              const value = colors[field.key] ?? [128, 128, 128];
              return (
                <div key={field.key} style={{ textAlign: "center" }}>
                  <input
                    type="color"
                    value={rgbToHex(value)}
                    onChange={(e) => {
                      const next = { ...colors, [field.key]: hexToRgb(e.target.value) };
                      patch(selected.id, { colors: next });
                    }}
                    style={{ width: 40, height: 40, border: "none", background: "none" }}
                  />
                  <div style={{ fontSize: "0.75rem" }}>{field.label}</div>
                </div>
              );
            })}
          </div>

          <h2>Cover slide text</h2>
          <CoverEditor
            cover={JSON.parse(selected.cover || "{}")}
            onSave={(cover) => patch(selected.id, { cover })}
          />

          <h2>Video &amp; captions</h2>
          <div className="field-row">
            <div className="field">
              <label>Resolution</label>
              <input
                type="text"
                defaultValue={`${selected.width}x${selected.height}`}
                onBlur={(e) => {
                  const [w, h] = e.target.value.split("x").map((v) => parseInt(v.trim(), 10));
                  if (w && h) patch(selected.id, { width: w, height: h });
                }}
              />
            </div>
            <div className="field">
              <label>Captions</label>
              <select
                value={selected.captionsEnabled ? "on" : "off"}
                onChange={(e) => patch(selected.id, { captionsEnabled: e.target.value === "on" })}
              >
                <option value="off">Off</option>
                <option value="on">Burned-in captions</option>
              </select>
            </div>
          </div>

          <h2>Assets</h2>
          <div className="field-row">
            <div className="field">
              <label>Logo (overlaid top-right on every slide)</label>
              <input
                ref={logoInput}
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadAsset(selected.id, "logo", file);
                }}
              />
              {selected.logoPath && <p className="page-subtitle">Current: {selected.logoPath.split("/").pop()}</p>}
            </div>
            <div className="field">
              <label>Intro video (spliced before the slideshow)</label>
              <input
                ref={introInput}
                type="file"
                accept="video/*"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadAsset(selected.id, "intro", file);
                }}
              />
              {selected.introVideoPath && (
                <p className="page-subtitle">Current: {selected.introVideoPath.split("/").pop()}</p>
              )}
            </div>
            <div className="field">
              <label>Outro video (spliced after the slideshow)</label>
              <input
                ref={outroInput}
                type="file"
                accept="video/*"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadAsset(selected.id, "outro", file);
                }}
              />
              {selected.outroVideoPath && (
                <p className="page-subtitle">Current: {selected.outroVideoPath.split("/").pop()}</p>
              )}
            </div>
          </div>

          <button className="danger" onClick={() => deleteTemplate(selected.id)}>
            Delete this template
          </button>
        </div>
      )}
    </div>
  );
}

function CoverEditor({ cover, onSave }: { cover: { kicker?: string; bullets?: string[] }; onSave: (c: unknown) => void }) {
  const [kicker, setKicker] = useState(cover.kicker ?? "");
  const [bullets, setBullets] = useState<string[]>(cover.bullets ?? ["", "", ""]);

  return (
    <div>
      <div className="field">
        <label>Kicker text</label>
        <input type="text" value={kicker} onChange={(e) => setKicker(e.target.value)} />
      </div>
      <div className="field-row">
        {[0, 1, 2].map((i) => (
          <div className="field" key={i}>
            <label>Bullet {i + 1}</label>
            <input
              type="text"
              value={bullets[i] ?? ""}
              onChange={(e) => {
                const next = [...bullets];
                next[i] = e.target.value;
                setBullets(next);
              }}
            />
          </div>
        ))}
      </div>
      <button className="secondary" onClick={() => onSave({ kicker, bullets })}>
        Save cover text
      </button>
    </div>
  );
}
