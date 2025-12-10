import { useEffect, useState } from "react";

export function DeviceCard({ name, baseUrl }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  async function fetchStatus() {
    try {
      const res = await fetch(`${baseUrl}/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 2000);
    return () => clearInterval(id);
  }, [baseUrl]);

  async function startSequence(seq) {
    try {
      await fetch(`${baseUrl}/command/start/${seq}`, { method: "POST" });
      fetchStatus();
    } catch (e) {
      setError(e.message);
    }
  }

  async function emergencyStop() {
    try {
      await fetch(`${baseUrl}/command/emergency_stop`, { method: "POST" });
      fetchStatus();
    } catch (e) {
      setError(e.message);
    }
  }

  const state = status?.state ?? "UNKNOWN";

  return (
    <div className="bg-white border rounded-xl shadow p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{name}</h2>
        <span
          className={`px-2 py-1 rounded text-xs font-semibold ${
            state === "RUNNING"
              ? "bg-green-100 text-green-700"
              : state === "ERROR"
              ? "bg-red-100 text-red-700"
              : "bg-gray-100 text-gray-700"
          }`}
        >
          {state}
        </span>
      </div>

      {error && <p className="text-sm text-red-600">Error: {error}</p>}

      {status && (
        <div className="text-sm space-y-1">
          <p><strong>Device ID:</strong> {status.device_id}</p>
          <p><strong>Sequence:</strong> {status.current_sequence ?? "—"}</p>
          <p><strong>Pressure:</strong> {status.pressure_bar}</p>
          <p><strong>Flow:</strong> {status.flow_lpm}</p>
          <p><strong>Volume:</strong> {status.total_volume_l}</p>
          <p><strong>Last error:</strong> {status.last_error ?? "None"}</p>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => startSequence("clean_1")}
          className="px-3 py-2 bg-blue-500 text-white rounded text-sm"
        >
          Clean 1
        </button>
        <button
          onClick={() => startSequence("concentration")}
          className="px-3 py-2 bg-indigo-500 text-white rounded text-sm"
        >
          Concentration
        </button>
        <button
          onClick={emergencyStop}
          className="px-3 py-2 bg-red-500 text-white rounded text-sm ml-auto"
        >
          STOP
        </button>
      </div>
    </div>
  );
}
