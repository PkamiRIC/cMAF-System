"use client"

type Props = {
  activePort: number
  onSelect?: (port: number) => void
  locked?: boolean
}

export default function RotaryValveWidget({ activePort, onSelect, locked }: Props) {
  const ports = [1, 2, 3, 4, 5, 6]

  const getPortPosition = (index: number) => {
    const angle = (index * 360) / 6 - 90
    const radius = 80
    const x = Math.cos((angle * Math.PI) / 180) * radius
    const y = Math.sin((angle * Math.PI) / 180) * radius
    return { x, y }
  }

  return (
    <div className="premium-card p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-foreground">Rotary Valve</h2>
        <span className="px-4 py-2 bg-primary/15 border border-primary/30 rounded-lg text-primary font-semibold shadow-sm">
          Port {activePort}
        </span>
      </div>

      <div className="flex justify-center items-center py-4">
        <svg width="280" height="280" viewBox="0 0 280 280" className="drop-shadow-xl">
          <defs>
            <radialGradient id="bgGradient" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgb(30, 41, 59)" stopOpacity="1" />
              <stop offset="100%" stopColor="rgb(15, 23, 42)" stopOpacity="1" />
            </radialGradient>
          </defs>
          <circle cx="140" cy="140" r="130" fill="url(#bgGradient)" stroke="rgb(71, 85, 105)" strokeWidth="2" />

          <circle
            cx="140"
            cy="140"
            r="45"
            fill="rgb(30, 58, 138)"
            stroke="rgb(59, 130, 246)"
            strokeWidth="4"
            className="drop-shadow-lg"
          />

          <g>
            <line
              x1="140"
              y1="140"
              x2="140"
              y2="65"
              stroke="rgb(96, 165, 250)"
              strokeWidth="4"
              strokeLinecap="round"
              className="drop-shadow-lg"
              style={{
                transform: `rotate(${((activePort - 1) * 360) / 6}deg)`,
                transformOrigin: "140px 140px",
                transition: "transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            />
          </g>

          {ports.map((port, index) => {
            const pos = getPortPosition(index)
            const isActive = port === activePort
            return (
              <g
                key={port}
                onClick={() => !locked && onSelect?.(port)}
                style={{ cursor: locked ? "not-allowed" : "pointer" }}
              >
                <circle
                  cx={140 + pos.x}
                  cy={140 + pos.y}
                  r="28"
                  fill={isActive ? "rgb(59, 130, 246)" : "rgb(30, 58, 138)"}
                  stroke={isActive ? "rgb(147, 197, 253)" : "rgb(71, 85, 105)"}
                  strokeWidth="3"
                  className={isActive ? "drop-shadow-lg" : ""}
                  style={{ transition: "all 0.3s ease", opacity: locked && !isActive ? 0.4 : 1 }}
                />
                <text
                  x={140 + pos.x}
                  y={140 + pos.y + 8}
                  textAnchor="middle"
                  fill="white"
                  fontSize="20"
                  fontWeight="bold"
                  style={{ pointerEvents: "none" }}
                >
                  {port}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <p className="text-sm text-muted-foreground text-center font-medium">
        {locked ? "Sequence running (locked)" : "Click any port to select"}
      </p>
    </div>
  )
}
