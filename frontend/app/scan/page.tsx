"use client";

import { useState } from "react";

type SemgrepFinding = {
  check_id?: string;
  path?: string;
  start?: {
    line?: number;
    col?: number;
  };
  end?: {
    line?: number;
    col?: number;
  };
  extra?: {
    message?: string;
    severity?: string;
    metadata?: Record<string, unknown>;
  };
};

type ScanResponse = {
  scan_id: string;
  status: "completed" | "failed" | "pending";
  total_findings?: number;
  findings?: SemgrepFinding[];
  error?: string;
};

export default function ScanPage() {
  const [inputType, setInputType] = useState("github");
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [error, setError] = useState("");

  const handleSubmit = async (
    e: React.SubmitEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    setLoading(true);
    setError("");
    setScanResult(null);

    try {
      const res = await fetch("http://localhost:8000/api/scans", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input_type: inputType,
          input_value: inputValue,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.detail || data.error || "Failed to start scan"
        );
      }

      setScanResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8">
      <div className="mx-auto w-full max-w-3xl">
        <form
          onSubmit={handleSubmit}
          className="mx-auto max-w-md space-y-4"
        >
          <h1 className="text-3xl font-bold">
            Start a Scan
          </h1>

          <select
            value={inputType}
            onChange={(e) => setInputType(e.target.value)}
            className="w-full rounded border p-2"
          >
            <option value="github">
              GitHub Repository
            </option>
            <option value="url">Live URL</option>
            <option value="zip">ZIP File</option>
            <option value="docker">Docker Image</option>
          </select>

          <input
            type="text"
            placeholder="https://github.com/user/repo"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            className="w-full rounded border p-2"
            required
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-blue-600 p-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Scanning..." : "Start Scan"}
          </button>
        </form>

        {error && (
          <div className="mx-auto mt-6 max-w-3xl rounded border border-red-300 bg-red-100 p-4 text-red-800">
            <p className="font-semibold">Scan failed</p>
            <p>{error}</p>
          </div>
        )}

        {scanResult && (
          <section className="mt-8">
            <div className="rounded bg-green-100 p-4">
              <p className="font-semibold">
                {scanResult.status === "completed"
                  ? "✅ Scan completed"
                  : "⚠️ Scan finished with an error"}
              </p>

              <p className="text-sm">
                Scan ID: {scanResult.scan_id}
              </p>

              <p className="text-sm">
                Total findings:{" "}
                {scanResult.total_findings ?? 0}
              </p>
            </div>

            <h2 className="mt-6 text-2xl font-semibold">
              Semgrep Findings
            </h2>

            {!scanResult.findings ||
            scanResult.findings.length === 0 ? (
              <p className="mt-3 rounded bg-gray-100 p-4">
                No findings detected.
              </p>
            ) : (
              <div className="mt-4 space-y-4">
                {scanResult.findings.map((finding, index) => (
                  <article
                    key={`${finding.check_id}-${finding.path}-${index}`}
                    className="rounded border bg-white p-4 shadow-sm"
                  >
                    <h3 className="font-semibold text-red-700">
                      {finding.extra?.message ||
                        finding.check_id ||
                        "Finding"}
                    </h3>

                    <dl className="mt-2 space-y-1 text-sm">
                      <div>
                        <dt className="inline font-medium">
                          Rule:{" "}
                        </dt>
                        <dd className="inline">
                          {finding.check_id || "Unknown"}
                        </dd>
                      </div>

                      <div>
                        <dt className="inline font-medium">
                          File:{" "}
                        </dt>
                        <dd className="inline">
                          {finding.path || "Unknown"}
                        </dd>
                      </div>

                      <div>
                        <dt className="inline font-medium">
                          Location:{" "}
                        </dt>
                        <dd className="inline">
                          Line{" "}
                          {finding.start?.line ?? "?"}
                          {finding.start?.col
                            ? `, column ${finding.start.col}`
                            : ""}
                        </dd>
                      </div>

                      <div>
                        <dt className="inline font-medium">
                          Severity:{" "}
                        </dt>
                        <dd className="inline">
                          {finding.extra?.severity ||
                            "Unknown"}
                        </dd>
                      </div>
                    </dl>

                    <details className="mt-3">
                      <summary className="cursor-pointer text-sm font-medium">
                        View raw finding
                      </summary>

                      <pre className="mt-2 overflow-auto rounded bg-gray-100 p-3 text-xs">
                        {JSON.stringify(finding, null, 2)}
                      </pre>
                    </details>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}