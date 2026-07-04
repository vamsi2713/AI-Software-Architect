import { useState } from "react";
import "./App.css";

const API_BASE = "https://ai-software-architect.onrender.com";

function UploadTab() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/ingest/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || `Server returned ${res.status}`);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p>Upload a .zip of a Python codebase to analyze it.</p>
      <div className="input-row">
        <input
          type="file"
          accept=".zip"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={runUpload} disabled={loading || !file}>
          {loading ? "Ingesting..." : "Upload & Analyze"}
        </button>
      </div>

      {error && <p className="error">Error: {error}</p>}

      {result && (
        <div className="result">
          <p>Ingestion complete:</p>
          <ul>
            <li>Files processed: {result.files_processed}</li>
            <li>Nodes written: {result.nodes_written}</li>
            <li>Relationships written: {result.relationships_written}</li>
            <li>Embedding failures: {result.embedding_failures}</li>
          </ul>
        </div>
      )}
    </div>
  );
}

function QueryTab() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runQuery = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const url = `${API_BASE}/query?question=${encodeURIComponent(question)}`;
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="input-row">
        <input
          type="text"
          placeholder="Ask a question about your codebase..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runQuery()}
        />
        <button onClick={runQuery} disabled={loading}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {error && <p className="error">Error: {error}</p>}

      {result && (
        <div className="result">
          {result.agent_used && (
            <span className="badge">{result.agent_used.replace("_", " ")}</span>
          )}
          <p className="answer">{result.answer}</p>

          <details>
            <summary>
              Raw retrieved context ({result.results?.length ?? 0} matches)
            </summary>
            <pre>{JSON.stringify(result.results, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

function ImpactTab() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runImpact = async () => {
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const url = `${API_BASE}/impact?name=${encodeURIComponent(name)}`;
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || `Server returned ${res.status}`);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="input-row">
        <input
          type="text"
          placeholder="Function or method name, e.g. write_okf_nodes"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runImpact()}
        />
        <button onClick={runImpact} disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>

      {error && <p className="error">Error: {error}</p>}

      {result?.ambiguous && (
        <div className="result">
          <p>
            Multiple nodes named "{result.name}" found - re-search using the
            exact id:
          </p>
          <ul>
            {result.matches.map((m) => (
              <li key={m.id}>
                <code>{m.id}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result && !result.ambiguous && (
        <div className="result">
          <p>
            <strong>{result.total_dependents}</strong> thing(s) transitively
            depend on <code>{result.target.name}</code>
          </p>
          {result.dependents.length === 0 ? (
            <p>
              Nothing else in the codebase calls this - safe to change in
              isolation.
            </p>
          ) : (
            <ul>
              {result.dependents.map((d) => (
                <li key={d.id}>
                  <strong>
                    {d.hops} hop{d.hops > 1 ? "s" : ""}
                  </strong>{" "}
                  away: {d.name}
                  <br />
                  <code className="filepath">{d.file_path}</code>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function App() {
  const [tab, setTab] = useState("query");

  return (
    <div className="app">
      <h1>AI Software Architect</h1>
      <div className="tabs">
        <button
          className={tab === "query" ? "active" : ""}
          onClick={() => setTab("query")}
        >
          Query
        </button>
        <button
          className={tab === "impact" ? "active" : ""}
          onClick={() => setTab("impact")}
        >
          Impact Analysis
        </button>
        <button
          className={tab === "upload" ? "active" : ""}
          onClick={() => setTab("upload")}
        >
          Upload
        </button>
      </div>

      {tab === "query" && <QueryTab />}
      {tab === "impact" && <ImpactTab />}
      {tab === "upload" && <UploadTab />}
    </div>
  );
}

export default App;
