import { useEffect, useState } from "react";

export function DeviceCard({ name, baseUrl }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!baseUrl) {
      setError("No backend URL configured");
      return;
    }

    let cancelled = false;

    async function fetchStatus() {
      try {
        const res = await fetch(`${baseUrl}/status`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to fetch status");
        }
      }
    }

    fetchStatus();
    const id = setInterval(fetchStatus, 2000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [baseUrl]);

  return (
    <div className="border rounded-lg p-4 shadow-sm bg-white flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{name}</h2>
      <p className="text-xs text-gray-500 break-all">{baseUrl}</p>

      {error && (
        <div className="text-xs text-red-600">
          Error: {error}
        </div>
      )}

      {status ? (
        <div className="text-sm space-y-1">
          <div>
            <span className="font-semibold">State:</span>{" "}
            <span>{status.state}</span>
          </div>
          <div>
            <span className="font-semibold">Sequence:</span>{" "}
            <span>{status.current_sequence || "-"}</span>
          </div>
          <div>
            <span className="font-semibold">Pressure (bar):</span>{" "}
            <span>{status.pressure_bar}</span>
          </div>
          <div>
            <span className="font-semibold">Flow (L/min):</span>{" "}
            <span>{status.flow_lpm}</span>
          </div>
          <div>
            <span className="font-semibold">Total Volume (L):</span>{" "}
            <span>{status.total_volume_l}</span>
          </div>
          {status.last_error && (
            <div className="text-xs text-red-500">
              Last error: {status.last_error}
            </div>
          )}
        </div>
      ) : !error ? (
        <div className="text-sm text-gray-500">Loading status…</div>
      ) : null}
    </div>
  );
}
