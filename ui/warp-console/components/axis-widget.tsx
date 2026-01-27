"use client"

import { useState, useEffect } from "react"

type Orientation = "vertical" | "horizontal"

interface AxisWidgetProps {
  axisId: "X" | "Z"
  name: string
  orientation: Orientation
  positionMm: number
  minMm: number
  maxMm: number
  targetMm?: number
  velocityMmPerS?: number
  homed: boolean
  homedDimmed?: boolean
  onPosition1?: () => void
  onPosition2?: () => void
  onPosition3?: () => void
  position1Label?: string
  position2Label?: string
  position3Label?: string
  onHome?: () => void
  onMove?: () => void
  position: number
  speed: number
  onPositionChange: (value: number) => void
  onSpeedChange: (value: number) => void
}

export default function AxisWidget({
  axisId,
  name,
  orientation,
  positionMm,
  minMm,
  maxMm,
  targetMm,
  velocityMmPerS,
  homed,
  homedDimmed = false,
  onPosition1,
  onPosition2,
  onPosition3,
  position1Label,
  position2Label,
  position3Label,
  onHome,
  onMove,
  position,
  speed,
  onPositionChange,
  onSpeedChange,
}: AxisWidgetProps) {
  const [displayPos, setDisplayPos] = useState(positionMm)

  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayPos((prev) => {
        const diff = positionMm - prev
        if (Math.abs(diff) < 0.1) return positionMm
        return prev + diff * 0.15
      })
    }, 30)
    return () => clearInterval(interval)
  }, [positionMm])

  const range = maxMm - minMm || 1
  const clampedPos = Math.min(Math.max(displayPos, minMm), maxMm)
  const fraction = (clampedPos - minMm) / range

  const carriageStyle =
    orientation === "vertical" ? { top: `${100 - fraction * 100}%` } : { left: `${fraction * 100}%` }

  return (
    <div className="premium-card p-6 space-y-4">
      {/* Header */}
      <div className="flex justify-between items-start gap-3">
        <div>
          <h3 className="text-xl font-bold text-foreground">{axisId} Axis</h3>
          <p className="text-sm text-muted-foreground mt-1">{name}</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <span
            className={`text-xs px-3 py-1 rounded-full font-semibold uppercase tracking-wide shadow-sm transition ${
              homed
                ? homedDimmed
                  ? "bg-success/10 text-success/70 border border-success/20 opacity-60"
                  : "bg-success/20 text-success border border-success/40 shadow-success/40"
                : "bg-muted text-muted-foreground border border-border"
            }`}
          >
            {homed ? "Homed" : "Not Homed"}
          </span>
        </div>
      </div>

      {/* Body: Track + Controls */}
      <div className="flex gap-6 items-stretch">
        <div className="relative">
          {orientation === "vertical" ? (
            <div className="w-12 h-52 bg-gradient-to-b from-muted to-secondary rounded-2xl border border-border flex items-center justify-center shadow-inner">
              <div className="absolute top-3 text-xs font-medium text-muted-foreground">TOP</div>
              <div
                className="absolute w-7 h-7 bg-gradient-to-br from-primary to-accent rounded-lg shadow-lg shadow-primary/40 border border-primary/20 transition-all duration-300"
                style={carriageStyle}
              />
              <div className="absolute bottom-3 text-xs font-medium text-muted-foreground">BOT</div>
            </div>
          ) : (
            <div className="w-52 h-12 bg-gradient-to-r from-muted to-secondary rounded-2xl border border-border flex items-center justify-center shadow-inner">
              <div className="absolute left-3 text-xs font-medium text-muted-foreground">LEFT</div>
              <div
                className="absolute w-7 h-7 bg-gradient-to-br from-primary to-accent rounded-lg shadow-lg shadow-primary/40 border border-primary/20 transition-all duration-300"
                style={carriageStyle}
              />
              <div className="absolute right-3 text-xs font-medium text-muted-foreground">RIGHT</div>
            </div>
          )}
        </div>

        {/* Readouts and controls */}
        <div className="flex flex-col justify-between flex-1 min-w-0">
          <div className="space-y-2">
            <div className="flex justify-between items-baseline gap-3">
              <span className="text-sm text-muted-foreground font-medium">Position</span>
              <span className="text-lg text-foreground font-semibold">{displayPos.toFixed(2)} mm</span>
            </div>
            {typeof targetMm === "number" && (
              <div className="flex justify-between items-baseline gap-3">
                <span className="text-sm text-muted-foreground font-medium">Target</span>
                <span className="text-lg text-primary font-semibold">{targetMm.toFixed(2)} mm</span>
              </div>
            )}
            {typeof velocityMmPerS === "number" && (
              <div className="flex justify-between items-baseline gap-3">
                <span className="text-sm text-muted-foreground font-medium">Velocity</span>
                <span className="text-lg text-accent font-semibold">{velocityMmPerS.toFixed(1)} mm/s</span>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted-foreground font-medium w-16">Pos</label>
              <input
                type="number"
                value={position}
                onChange={(e) => onPositionChange(Number.parseFloat(e.target.value) || 0)}
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
              <span className="text-sm text-muted-foreground">mm</span>
            </div>
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted-foreground font-medium w-16">Speed</label>
              <input
                type="number"
                value={speed}
                onChange={(e) => onSpeedChange(Number.parseFloat(e.target.value) || 0)}
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
              <span className="text-sm text-muted-foreground">RPM</span>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              onClick={onHome}
              disabled={!onHome}
              className="px-3 py-2 text-sm font-medium bg-secondary text-secondary-foreground rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Home
            </button>
            <button
              onClick={onMove}
              disabled={!onMove}
              className="px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/20"
            >
              Move
            </button>
            <button
              onClick={onPosition1}
              disabled={!onPosition1}
              className="px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/20"
            >
              {position1Label || "Pos 1"}
            </button>
            <button
              onClick={onPosition2}
              disabled={!onPosition2}
              className="px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/20"
            >
              {position2Label || "Pos 2"}
            </button>
            <button
              onClick={onPosition3}
              disabled={!onPosition3}
              className="px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-primary/20"
            >
              {position3Label || "Pos 3"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
