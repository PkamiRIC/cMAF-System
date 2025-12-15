"use client"

import { useEffect, useState } from "react"
import type { DeviceStatus } from "./status-display"
import AxisWidget from "./axis-widget"
import SyringeWidget from "./syringe-widget"

// Ensure we talk directly to the PLC by default.
const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://warp3plc.local:8003"

async function post(path: string, body?: any) {
  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`)
}

async function fetchStatus(): Promise<DeviceStatus> {
  const res = await fetch(`${apiBase}/status`)
  if (!res.ok) throw new Error(`status failed (${res.status})`)
  return res.json()
}

export default function ControlPanel() {
  const [verticalPos, setVerticalPos] = useState(25.0)
  const [verticalTarget, setVerticalTarget] = useState(50.0)
  const [verticalVelocity, setVerticalVelocity] = useState(40.0)
  const [verticalHomed, setVerticalHomed] = useState(true)
  const [verticalEnabled, setVerticalEnabled] = useState(true)
  const [verticalFault, setVerticalFault] = useState(false)
  const [verticalPosition, setVerticalPosition] = useState(50.0)
  const [verticalSpeed, setVerticalSpeed] = useState(5.0)
  const verticalMin = 0
  const verticalMax = 33

  const [horizontalPos, setHorizontalPos] = useState(60.0)
  const [horizontalTarget, setHorizontalTarget] = useState(100.0)
  const [horizontalVelocity, setHorizontalVelocity] = useState(60.0)
  const [horizontalHomed, setHorizontalHomed] = useState(true)
  const [horizontalEnabled, setHorizontalEnabled] = useState(true)
  const [horizontalFault, setHorizontalFault] = useState(false)
  const [horizontalPosition, setHorizontalPosition] = useState(100.0)
  const [horizontalSpeed, setHorizontalSpeed] = useState(5.0)
  const horizontalMin = 0
  const horizontalMax = 300

  const [syringeVolume, setSyringeVolume] = useState(2.5)
  const [flowRate, setFlowRate] = useState(1.0)
  const [isSyringeActive, setIsSyringeActive] = useState(false)
  const [syringeLiveVolume, setSyringeLiveVolume] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [relayStates, setRelayStates] = useState<boolean[]>(Array(8).fill(false))

  const toggleRelay = async (index: number) => {
    const desired = !relayStates[index]
    try {
      await post(`/relays/${index + 1}/${desired ? "on" : "off"}`)
      const newStates = [...relayStates]
      newStates[index] = desired
      setRelayStates(newStates)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Relay toggle failed")
    }
  }

  const toggleAllRelays = async (state: boolean) => {
    try {
      await post(`/relays/all/${state ? "on" : "off"}`)
      setRelayStates(Array(8).fill(state))
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Relay toggle failed")
    }
  }

  const handleSyringeMove = async (target: number) => {
    try {
      await post("/syringe/move", { volume_ml: target, flow_ml_min: flowRate })
      setIsSyringeActive(true)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Syringe command failed")
    }
  }

  const handleSyringeStop = async () => {
    try {
      await post("/syringe/stop")
      setIsSyringeActive(false)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Syringe stop failed")
    }
  }

  const handleSyringeHome = async () => {
    try {
      await post("/syringe/home")
      setIsSyringeActive(true)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Syringe home failed")
    }
  }

  const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val))

  const moveAxis = async (axis: "X" | "Z", position: number, rpm: number) => {
    try {
      await post(`/axis/${axis}/move`, { position_mm: position, rpm })
      setError(null)
    } catch (err: any) {
      setError(err?.message || `${axis} move failed`)
    }
  }

  const homeAxis = async (axis: "X" | "Z") => {
    try {
      await post(`/axis/${axis}/home`)
      setError(null)
    } catch (err: any) {
      setError(err?.message || `${axis} home failed`)
    }
  }

  // Poll status so syringe activity reflects the real driver status.
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const data = await fetchStatus()
        if (!cancelled) {
          setIsSyringeActive(Boolean(data.syringe_busy))
          if (typeof data.syringe_volume_ml === "number") {
            setSyringeLiveVolume(Number(data.syringe_volume_ml.toFixed(2)))
          }
        }
      } catch (err) {
        // Swallow polling errors; UI handles command errors separately.
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AxisWidget
          axisId="Z"
          name="Vertical Axis – Device 3"
          orientation="vertical"
          positionMm={verticalPos}
          minMm={verticalMin}
          maxMm={verticalMax}
          targetMm={verticalTarget}
          velocityMmPerS={verticalVelocity}
          homed={verticalHomed}
          enabled={verticalEnabled}
          fault={verticalFault}
          onPosition1={() => {
            const target = clamp(0, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
          onPosition2={() => {
            const target = clamp(15, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
          onPosition3={() => {
            const target = clamp(33, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
          onHome={() => {
            setVerticalPos(verticalMin)
            homeAxis("Z")
          }}
          position={verticalPosition}
          speed={verticalSpeed}
          onPositionChange={(val) => setVerticalPosition(clamp(val, verticalMin, verticalMax))}
          onSpeedChange={setVerticalSpeed}
          onMove={() => {
            const target = clamp(verticalPosition, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
        />

        <AxisWidget
          axisId="X"
          name="Horizontal Axis – Device 3"
          orientation="horizontal"
          positionMm={horizontalPos}
          minMm={horizontalMin}
          maxMm={horizontalMax}
          targetMm={horizontalTarget}
          velocityMmPerS={horizontalVelocity}
          homed={horizontalHomed}
          enabled={horizontalEnabled}
          fault={horizontalFault}
          onPosition1={() => {
            const target = clamp(100, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
          onPosition2={() => {
            const target = clamp(200, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
          onPosition3={() => {
            const target = clamp(280, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
          onHome={() => {
            setHorizontalPos(horizontalMin)
            homeAxis("X")
          }}
          position={horizontalPosition}
          speed={horizontalSpeed}
          onPositionChange={(val) => setHorizontalPosition(clamp(val, horizontalMin, horizontalMax))}
          onSpeedChange={setHorizontalSpeed}
          onMove={() => {
            const target = clamp(horizontalPosition, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="premium-card p-6 flex items-center justify-center">
          <SyringeWidget volume={syringeLiveVolume ?? syringeVolume} maxVolume={2.5} isActive={isSyringeActive} />
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Syringe Control</h2>
          <p className="text-sm text-muted-foreground">
            Status:{" "}
            <span className={isSyringeActive ? "text-success font-medium" : "text-muted-foreground"}>
              {isSyringeActive ? "Active" : "Idle"}
            </span>
          </p>

          <div className="space-y-3">
            <div>
              <label className="text-sm text-muted-foreground block mb-2">Volume (mL)</label>
              <input
                type="number"
                value={syringeVolume}
                onChange={(e) =>
                  setSyringeVolume(Math.min(2.5, Math.max(0, Number.parseFloat(e.target.value) || 0)))
                }
                min="0"
                max="2.5"
                step="0.1"
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground block mb-2">Flow Rate (mL/min)</label>
              <input
                type="number"
                value={flowRate}
                onChange={(e) => setFlowRate(Number.parseFloat(e.target.value) || 0)}
                min="0"
                step="0.1"
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
            </div>

            <div className="grid grid-cols-3 gap-3 pt-2">
              <button
                onClick={() => handleSyringeMove(syringeVolume)}
                className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20"
              >
                Draw
              </button>
              <button
                onClick={handleSyringeStop}
                className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
              >
                Stop
              </button>
              <button
                onClick={handleSyringeHome}
                className="px-4 py-2.5 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-muted transition-all shadow-md"
              >
                Home
              </button>
            </div>
          </div>
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Relays</h2>

          <div className="grid grid-cols-4 gap-3">
            {relayStates.map((isActive, index) => (
              <button
                key={`relay-${index}`}
                onClick={() => toggleRelay(index)}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-all shadow-md ${
                  isActive
                    ? "bg-primary text-primary-foreground hover:opacity-90 shadow-primary/20"
                    : "bg-secondary text-secondary-foreground hover:bg-muted"
                }`}
              >
                R{index + 1}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <button
              onClick={() => toggleAllRelays(true)}
              className="px-4 py-2.5 bg-success text-success-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-success/20"
            >
              All ON
            </button>
            <button
              onClick={() => toggleAllRelays(false)}
              className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
            >
              All OFF
            </button>
          </div>

          {error && <div className="text-xs text-destructive font-semibold">{error}</div>}
        </div>
      </div>
    </div>
  )
}
