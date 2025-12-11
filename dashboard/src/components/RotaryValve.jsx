import { useEffect, useState } from "react";

export default function RotaryValve({ activePort = 1, onChange }) {
  const [current, setCurrent] = useState(activePort || 1);

  useEffect(() => {
    setCurrent(activePort || 1);
  }, [activePort]);

  const ports = [1, 2, 3, 4, 5, 6];
  const radius = 90;

  const handleSelect = (port) => {
    setCurrent(port);
    onChange?.(port);
  };

  return (
    <div style={styles.container}>
      <div style={styles.title}>Rotary Valve</div>
      <div style={styles.circle}>
        {ports.map((p, i) => {
          const angle = (360 / ports.length) * i - 90;
          const x = radius * Math.cos((angle * Math.PI) / 180);
          const y = radius * Math.sin((angle * Math.PI) / 180);
          const active = p === current;
          return (
            <button
              key={p}
              onClick={() => handleSelect(p)}
              style={{
                ...styles.port,
                transform: `translate(${x}px, ${y}px)`,
                background: active ? "#2563eb" : "#0f172a",
                color: active ? "#f8fafc" : "#e2e8f0",
                boxShadow: active ? "0 0 0 6px rgba(37,99,235,0.25)" : "none",
              }}
            >
              {p}
            </button>
          );
        })}
        <div style={styles.core}>
          <div style={styles.coreLabel}>Port</div>
          <div style={styles.coreValue}>{current}</div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    width: 260,
    padding: 16,
    background: "#0b1224",
    border: "1px solid #1e293b",
    borderRadius: 16,
    color: "#e2e8f0",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  title: {
    fontWeight: 600,
    letterSpacing: 0.2,
    marginBottom: 12,
  },
  circle: {
    position: "relative",
    width: 220,
    height: 220,
    margin: "0 auto",
    borderRadius: "50%",
    background: "radial-gradient(circle at 50% 50%, #0f172a 0%, #0b1224 70%)",
    border: "1px solid #1f2937",
    display: "grid",
    placeItems: "center",
  },
  port: {
    position: "absolute",
    width: 56,
    height: 56,
    borderRadius: "50%",
    border: "1px solid #334155",
    cursor: "pointer",
    transition: "all 0.2s ease",
    fontWeight: 700,
    letterSpacing: 0.3,
  },
  core: {
    width: 80,
    height: 80,
    borderRadius: "50%",
    background: "#111827",
    border: "1px solid #1f2937",
    display: "grid",
    placeItems: "center",
    gap: 4,
  },
  coreLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    color: "#94a3b8",
    letterSpacing: 0.8,
  },
  coreValue: {
    fontSize: 24,
    fontWeight: 800,
    color: "#38bdf8",
    lineHeight: 1,
  },
};
