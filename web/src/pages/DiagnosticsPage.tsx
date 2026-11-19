import { useEffect, useState } from "react";
import { api, ApiError } from "../api";

interface ConfigStatus {
  elevenLabs: boolean;
  aws: boolean;
  bunny: boolean;
  moodle: boolean;
}

interface TestResult {
  ok: boolean;
  message: string;
}

export default function DiagnosticsPage() {
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [results, setResults] = useState<Record<string, TestResult | undefined>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [bucket, setBucket] = useState("");
  const [region, setRegion] = useState("");
  const [libraryId, setLibraryId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ConfigStatus>("/diagnostics/config")
      .then(setConfig)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load diagnostics."));
  }, []);

  async function run(key: string, path: string, body?: unknown) {
    setTesting((t) => ({ ...t, [key]: true }));
    try {
      const result = await api.post<TestResult>(path, body);
      setResults((r) => ({ ...r, [key]: result }));
    } catch (err) {
      setResults((r) => ({ ...r, [key]: { ok: false, message: err instanceof ApiError ? err.message : "Request failed." } }));
    } finally {
      setTesting((t) => ({ ...t, [key]: false }));
    }
  }

  function ResultBanner({ result }: { result?: TestResult }) {
    if (!result) return null;
    return <div className={result.ok ? "success-banner" : "error-banner"}>{result.message}</div>;
  }

  return (
    <div>
      <h1>Diagnostics</h1>
      <p className="page-subtitle">
        Test each integration against real credentials before trusting it in a full production run.
      </p>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <div className="card-row">
          <div>
            <strong>ElevenLabs</strong>
            <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
              {config?.elevenLabs ? "API key configured" : "ELEVENLABS_API_KEY not set"}
            </p>
          </div>
          <button disabled={!config?.elevenLabs || testing.elevenlabs} onClick={() => run("elevenlabs", "/diagnostics/test/elevenlabs")}>
            {testing.elevenlabs ? "Testing…" : "Test Connection"}
          </button>
        </div>
        <ResultBanner result={results.elevenlabs} />
      </div>

      <div className="card">
        <div className="card-row">
          <div>
            <strong>AWS S3</strong>
            <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
              {config?.aws ? "Credentials configured" : "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set"}
            </p>
          </div>
        </div>
        <div className="field-row" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Bucket to test</label>
            <input type="text" value={bucket} onChange={(e) => setBucket(e.target.value)} placeholder="my-course-videos" />
          </div>
          <div className="field">
            <label>Region (optional)</label>
            <input type="text" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" />
          </div>
        </div>
        <button
          disabled={!config?.aws || !bucket || testing.aws}
          onClick={() => run("aws", "/diagnostics/test/aws", { bucket, region: region || undefined })}
        >
          {testing.aws ? "Testing…" : "Test Connection"}
        </button>
        <p className="page-subtitle" style={{ marginTop: 8 }}>
          This writes and deletes a small marker object, not just checking the bucket exists — a
          read-only policy would otherwise look fine here and then fail every real upload.
        </p>
        <ResultBanner result={results.aws} />
      </div>

      <div className="card">
        <div className="card-row">
          <div>
            <strong>Bunny Stream</strong>
            <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
              {config?.bunny ? "API key configured" : "BUNNY_STREAM_API_KEY not set"}
            </p>
          </div>
        </div>
        <div className="field" style={{ marginTop: 12 }}>
          <label>Library ID to test</label>
          <input type="text" value={libraryId} onChange={(e) => setLibraryId(e.target.value)} placeholder="123456" />
        </div>
        <button disabled={!config?.bunny || !libraryId || testing.bunny} onClick={() => run("bunny", "/diagnostics/test/bunny", { libraryId })}>
          {testing.bunny ? "Testing…" : "Test Connection"}
        </button>
        <ResultBanner result={results.bunny} />
      </div>

      <div className="card">
        <div className="card-row">
          <div>
            <strong>Moodle</strong>
            <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
              {config?.moodle ? "Base URL + token configured" : "MOODLE_BASE_URL / MOODLE_TOKEN not set"}
            </p>
          </div>
          <button disabled={!config?.moodle || testing.moodle} onClick={() => run("moodle", "/diagnostics/test/moodle")}>
            {testing.moodle ? "Testing…" : "Test Connection"}
          </button>
        </div>
        <p className="page-subtitle" style={{ marginTop: 8 }}>
          Also checks that the token's role actually has the publish permission this app needs —
          a token can be valid and still lack that permission.
        </p>
        <ResultBanner result={results.moodle} />
      </div>
    </div>
  );
}
