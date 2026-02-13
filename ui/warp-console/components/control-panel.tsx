"use client"

import { useEffect, useState } from "react"
import type { DeviceStatus } from "./status-display"
import AxisWidget from "./axis-widget"
import SyringeWidget from "./syringe-widget"
import { getApiBase } from "../lib/api-base"

const apiBase = getApiBase()

async function post(path: string, body?: any) {
  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = ""
    try {
      const data = await res.json()
      if (data?.detail) detail = String(data.detail)
    } catch {}
    throw new Error(detail || `POST ${path} failed (${res.status})`)
  }
}

async function fetchStatus(): Promise<DeviceStatus> {
  const res = await fetch(`${apiBase}/status`)
  if (!res.ok) throw new Error(`status failed (${res.status})`)
  return res.json()
}

type ControlPanelProps = {
  targetVolumeMl: number
  setTargetVolumeMl: (value: number) => void
  setSequenceTempTargetDraft: (value: string) => void
}

export default function ControlPanel({
  targetVolumeMl,
  setTargetVolumeMl,
  setSequenceTempTargetDraft,
}: ControlPanelProps) {
  const [verticalPos, setVerticalPos] = useState(0.0)
  const [verticalTarget, setVerticalTarget] = useState(25.0)
  const [verticalVelocity, setVerticalVelocity] = useState(0.25)
  const [verticalHomed, setVerticalHomed] = useState(false)
  const [verticalHomedDimmed, setVerticalHomedDimmed] = useState(true)
  const [verticalPosition, setVerticalPosition] = useState(0.0)
  const [verticalSpeed, setVerticalSpeed] = useState(0.25)
  const verticalMin = 0
  const verticalMax = 25

  const [horizontalPos, setHorizontalPos] = useState(0.0)
  const [horizontalTarget, setHorizontalTarget] = useState(133.0)
  const [horizontalVelocity, setHorizontalVelocity] = useState(0.25)
  const [horizontalHomed, setHorizontalHomed] = useState(false)
  const [horizontalHomedDimmed, setHorizontalHomedDimmed] = useState(true)
  const [horizontalPosition, setHorizontalPosition] = useState(0.0)
  const [horizontalSpeed, setHorizontalSpeed] = useState(0.25)
  const horizontalMin = 0
  const horizontalMax = 133

  const [syringeVolume, setSyringeVolume] = useState(2.5)
  const [flowRate, setFlowRate] = useState(1.0)
  const [isSyringeActive, setIsSyringeActive] = useState(false)
  const [syringeLiveVolume, setSyringeLiveVolume] = useState<number | null>(null)
  const [syringeHomed, setSyringeHomed] = useState(false)
  const [syringeHomedDimmed, setSyringeHomedDimmed] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [relayStates, setRelayStates] = useState<boolean[]>(Array(8).fill(false))
  const [peristalticEnabled, setPeristalticEnabled] = useState(false)
  const [peristalticDirection, setPeristalticDirection] = useState(true)
  const [peristalticLowSpeed, setPeristalticLowSpeed] = useState(false)
  const [pidEnabled, setPidEnabled] = useState(false)
  const [pidSetpoint, setPidSetpoint] = useState(1.0)
  const [pidHall, setPidHall] = useState<number | null>(null)
  const [flowMlMin, setFlowMlMin] = useState(0.0)
  const [totalMl, setTotalMl] = useState(0.0)
  const [flowRunning, setFlowRunning] = useState(false)
  const [flowError, setFlowError] = useState<string | null>(null)
  const [tempEnabled, setTempEnabled] = useState(false)
  const [tempReady, setTempReady] = useState<boolean | null>(null)
  const [tempTargetC, setTempTargetC] = useState(58.0)
  const [tempTargetDraft, setTempTargetDraft] = useState("58.0")
  const [tempTargetEditing, setTempTargetEditing] = useState(false)
  const [tempCurrentC, setTempCurrentC] = useState<number | null>(null)
  const [tempError, setTempError] = useState<string | null>(null)

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

  const togglePeristalticEnable = async () => {
    const desired = !peristalticEnabled
    try {
      await post("/peristaltic/enable", { enabled: desired })
      setPeristalticEnabled(desired)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Peristaltic enable failed")
    }
  }

  const togglePeristalticDirection = async () => {
    const desired = !peristalticDirection
    try {
      await post("/peristaltic/direction", { forward: desired })
      setPeristalticDirection(desired)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Peristaltic direction failed")
    }
  }

  const togglePeristalticSpeed = async () => {
    const desired = !peristalticLowSpeed
    try {
      await post("/peristaltic/speed", { low_speed: desired })
      setPeristalticLowSpeed(desired)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Peristaltic speed failed")
    }
  }

  const togglePidEnable = async () => {
    const desired = !pidEnabled
    try {
      await post("/pid/enable", { enabled: desired })
      setPidEnabled(desired)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "PID enable failed")
    }
  }

  const applyPidSetpoint = async () => {
    try {
      await post("/pid/setpoint", { value: pidSetpoint })
      setError(null)
    } catch (err: any) {
      setError(err?.message || "PID setpoint failed")
    }
  }

  const pidHome = async () => {
    try {
      await post("/pid/home")
      setError(null)
    } catch (err: any) {
      setError(err?.message || "PID home failed")
    }
  }

  const pidClose = async () => {
    try {
      await post("/pid/close")
      setError(null)
    } catch (err: any) {
      setError(err?.message || "PID close failed")
    }
  }

  const flowStart = async () => {
    try {
      await post("/flow/start")
      const data = await fetchStatus()
      setFlowRunning(Boolean((data as any).flow_running))
      if (typeof (data as any).flow_ml_min === "number") {
        setFlowMlMin(Number((data as any).flow_ml_min))
      }
      if (typeof (data as any).total_ml === "number") {
        setTotalMl(Number((data as any).total_ml))
      }
      setFlowError(typeof (data as any).flow_error === "string" ? String((data as any).flow_error) : null)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Flow start failed")
    }
  }

  const flowStop = async () => {
    try {
      await post("/flow/stop")
      const data = await fetchStatus()
      setFlowRunning(Boolean((data as any).flow_running))
      if (typeof (data as any).flow_ml_min === "number") {
        setFlowMlMin(Number((data as any).flow_ml_min))
      }
      if (typeof (data as any).total_ml === "number") {
        setTotalMl(Number((data as any).total_ml))
      }
      setFlowError(typeof (data as any).flow_error === "string" ? String((data as any).flow_error) : null)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Flow stop failed")
    }
  }

  const flowReset = async () => {
    try {
      await post("/flow/reset")
      const data = await fetchStatus()
      if (typeof (data as any).flow_ml_min === "number") {
        setFlowMlMin(Number((data as any).flow_ml_min))
      }
      if (typeof (data as any).total_ml === "number") {
        setTotalMl(Number((data as any).total_ml))
      } else {
        setTotalMl(0)
      }
      setFlowRunning(Boolean((data as any).flow_running))
      setFlowError(typeof (data as any).flow_error === "string" ? String((data as any).flow_error) : null)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Flow reset failed")
    }
  }

  const tempToggle = async (enabled: boolean) => {
    try {
      await post("/temperature/enable", { enabled })
      const data = await fetchStatus()
      setTempEnabled(Boolean((data as any).temp_enabled))
      if (!tempTargetEditing && typeof (data as any).temp_target_c === "number") {
        const target = Number((data as any).temp_target_c)
        setTempTargetC(target)
        setTempTargetDraft(target.toFixed(1))
        setSequenceTempTargetDraft(target.toFixed(1))
      }
      if (typeof (data as any).temp_current_c === "number") {
        setTempCurrentC(Number((data as any).temp_current_c))
      } else {
        setTempCurrentC(null)
      }
      setTempError(typeof (data as any).temp_error === "string" ? String((data as any).temp_error) : null)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Temp control failed")
    }
  }

  const applyTempTarget = async () => {
    try {
      // Keep local draft protected from status polling during apply click.
      setTempTargetEditing(true)
      const parsed = Number.parseFloat(tempTargetDraft)
      if (!Number.isFinite(parsed)) {
        throw new Error("Invalid temperature target")
      }
      await post("/temperature/target", { value_c: parsed })
      const data = await fetchStatus()
      if (typeof (data as any).temp_target_c === "number") {
        const target = Number((data as any).temp_target_c)
        setTempTargetC(target)
        setTempTargetDraft(target.toFixed(1))
        setSequenceTempTargetDraft(target.toFixed(1))
      }
      setTempTargetEditing(false)
      if (typeof (data as any).temp_current_c === "number") {
        setTempCurrentC(Number((data as any).temp_current_c))
      } else {
        setTempCurrentC(null)
      }
      setTempError(typeof (data as any).temp_error === "string" ? String((data as any).temp_error) : null)
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Temp target failed")
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

  // Poll status so syringe activity and relays reflect the real driver status.
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
          // homed flags from backend
          const zH = Boolean((data as any).z_homed)
          const xH = Boolean((data as any).x_homed)
          setVerticalHomed(zH)
          setVerticalHomedDimmed(!zH)
          setHorizontalHomed(xH)
          setHorizontalHomedDimmed(!xH)
          const sH = Boolean((data as any).syringe_homed)
          setSyringeHomed(sH)
          setSyringeHomedDimmed(!sH)
          if (data.relay_states) {
            const arr = Array(8).fill(false)
            Object.entries(data.relay_states).forEach(([k, v]) => {
              const idx = Number(k) - 1
              if (idx >= 0 && idx < arr.length) arr[idx] = Boolean(v)
            })
            setRelayStates(arr)
          }
          setPeristalticEnabled(Boolean((data as any).peristaltic_enabled))
          setPeristalticDirection(Boolean((data as any).peristaltic_direction_cw))
          setPeristalticLowSpeed(Boolean((data as any).peristaltic_low_speed))
          setPidEnabled(Boolean((data as any).pid_enabled))
          if (typeof (data as any).pid_setpoint === "number") {
            setPidSetpoint(Number((data as any).pid_setpoint))
          }
          setPidHall(
            typeof (data as any).pid_hall === "number" ? Number((data as any).pid_hall) : null
          )
          if (typeof (data as any).flow_ml_min === "number") {
            setFlowMlMin(Number((data as any).flow_ml_min))
          }
          if (typeof (data as any).total_ml === "number") {
            setTotalMl(Number((data as any).total_ml))
          }
          setFlowRunning(Boolean((data as any).flow_running))
          setFlowError(typeof (data as any).flow_error === "string" ? String((data as any).flow_error) : null)
          setTempEnabled(Boolean((data as any).temp_enabled))
          if (!tempTargetEditing && typeof (data as any).temp_target_c === "number") {
            const target = Number((data as any).temp_target_c)
            setTempTargetC(target)
            setTempTargetDraft(target.toFixed(1))
            setSequenceTempTargetDraft(target.toFixed(1))
          }
          if (typeof (data as any).temp_current_c === "number") {
            setTempCurrentC(Number((data as any).temp_current_c))
          } else {
            setTempCurrentC(null)
          }
          setTempError(typeof (data as any).temp_error === "string" ? String((data as any).temp_error) : null)
          if (typeof (data as any).temp_ready === "boolean") {
            setTempReady(Boolean((data as any).temp_ready))
          } else {
            setTempReady(null)
          }
        }
      } catch {
        // Swallow polling errors; UI handles command errors separately.
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [tempTargetEditing])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AxisWidget
          axisId="Z"
          name="Vertical Axis"
          orientation="vertical"
          positionMm={verticalPos}
          minMm={verticalMin}
          maxMm={verticalMax}
          targetMm={verticalTarget}
          velocityMmPerS={verticalVelocity}
          homed={verticalHomed}
          homedDimmed={verticalHomedDimmed}
          onPosition1={() => {
            const target = clamp(0, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
          onPosition2={() => {
            const target = clamp(12.5, verticalMin, verticalMax)
            setVerticalPos(target)
            moveAxis("Z", target, verticalSpeed)
          }}
          onPosition3={() => {
            const target = clamp(25, verticalMin, verticalMax)
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
          position1Label="Open"
          position2Label="Mid"
          position3Label="Close"
        />

        <AxisWidget
          axisId="X"
          name="Horizontal Axis"
          orientation="horizontal"
          positionMm={horizontalPos}
          minMm={horizontalMin}
          maxMm={horizontalMax}
          targetMm={horizontalTarget}
          velocityMmPerS={horizontalVelocity}
          homed={horizontalHomed}
          homedDimmed={horizontalHomedDimmed}
          onPosition1={() => {
            const target = clamp(0, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
          onPosition2={() => {
            const target = clamp(26, horizontalMin, horizontalMax)
            setHorizontalPos(target)
            moveAxis("X", target, horizontalSpeed)
          }}
          onPosition3={() => {
            const target = clamp(133, horizontalMin, horizontalMax)
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
          position1Label="Filter In"
          position2Label="Filter Out"
          position3Label="Filtering"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="premium-card p-6 flex items-center justify-center">
          <div className="w-full">
            <div className="flex justify-end mb-3">
              <span
                className={`text-xs px-3 py-1 rounded-full font-semibold uppercase tracking-wide shadow-sm transition ${
                  syringeHomed
                    ? syringeHomedDimmed
                      ? "bg-success/10 text-success/60 border border-success/30 opacity-70"
                      : "bg-success/25 text-success border border-success/50 shadow-success/50"
                    : "bg-muted text-muted-foreground border border-border"
                }`}
              >
                {syringeHomed ? "Homed" : "Not Homed"}
              </span>
            </div>
            <SyringeWidget volume={syringeLiveVolume ?? syringeVolume} maxVolume={2.5} isActive={isSyringeActive} />
          </div>
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

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Peristaltic Pump</h2>
          <p className="text-sm text-muted-foreground">
            Status:{" "}
            <span className={peristalticEnabled ? "text-success font-medium" : "text-destructive font-medium"}>
              {peristalticEnabled ? "Enabled" : "Disabled"}
            </span>
          </p>
          <div className="space-y-3">
            <button
              onClick={togglePeristalticEnable}
              className="w-full px-4 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20"
            >
              {peristalticEnabled ? "Pump OFF" : "Pump ON"}
            </button>
            <button
              onClick={togglePeristalticDirection}
              className="w-full px-4 py-3 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-muted transition-all shadow-md"
            >
              Dir: {peristalticDirection ? "CW" : "CCW"}
            </button>
            <button
              onClick={togglePeristalticSpeed}
              className="w-full px-4 py-3 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-muted transition-all shadow-md"
            >
              {peristalticLowSpeed ? "Low Speed" : "High Speed"}
            </button>
          </div>
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">PID Valve</h2>
          <p className="text-sm text-muted-foreground">
            Feedback:{" "}
            <span className="text-foreground font-semibold">{flowMlMin.toFixed(2)} mL/min</span>
          </p>
          <p className="text-sm text-muted-foreground">
            Hall:{" "}
            <span className="text-foreground font-semibold">
              {pidHall === null ? "N/A" : pidHall ? "ON" : "OFF"}
            </span>
          </p>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted-foreground font-medium w-20">Setpoint</label>
              <input
                type="number"
                value={pidSetpoint}
                onChange={(e) => setPidSetpoint(Number.parseFloat(e.target.value) || 0)}
                step="0.1"
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
              <span className="text-sm text-muted-foreground">mL/min</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={togglePidEnable}
                className={`px-4 py-2.5 rounded-lg font-medium transition-all shadow-md ${
                  pidEnabled
                    ? "bg-success text-success-foreground shadow-success/20"
                    : "bg-secondary text-secondary-foreground hover:bg-muted"
                }`}
              >
                {pidEnabled ? "PID ON" : "Enable PID"}
              </button>
              <button
                onClick={applyPidSetpoint}
                className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20"
              >
                Apply
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={pidHome}
                className="px-4 py-2.5 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-muted transition-all shadow-md"
              >
                Home
              </button>
              <button
                onClick={pidClose}
                className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
              >
                Close
              </button>
            </div>
          </div>
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Temperature Control</h2>
          <p className="text-sm text-muted-foreground">
            Current:
            <span className="text-foreground font-semibold ml-2">
              {tempCurrentC === null ? "N/A" : `${tempCurrentC.toFixed(2)} °C`}
            </span>
          </p>
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            Ready:
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full border transition ${
                tempReady === null
                  ? "bg-muted border-border"
                  : tempReady
                  ? "bg-success border-success/60 shadow-sm shadow-success/40"
                  : "bg-muted border-border"
              }`}
              aria-label={tempReady === null ? "Temperature ready unknown" : tempReady ? "Temperature ready" : "Temperature not ready"}
              title={tempReady === null ? "N/A" : tempReady ? "Ready" : "Not ready"}
            />
            <span
              className={
                tempReady === null
                  ? "text-muted-foreground font-semibold"
                  : tempReady
                  ? "text-success font-semibold"
                  : "text-muted-foreground font-semibold"
              }
            >
              {tempReady === null ? "N/A" : tempReady ? "ON" : "OFF"}
            </span>
          </p>
          <div className="flex items-center gap-3">
            <label className="text-sm text-muted-foreground font-medium w-20">Target</label>
            <input
              type="number"
              value={tempTargetDraft}
              onFocus={() => setTempTargetEditing(true)}
              onBlur={() => setTempTargetEditing(false)}
              onChange={(e) => {
                setTempTargetDraft(e.target.value)
                setSequenceTempTargetDraft(e.target.value)
                const parsed = Number.parseFloat(e.target.value)
                if (Number.isFinite(parsed)) {
                  setTempTargetC(parsed)
                }
              }}
              step="0.1"
              className="w-28 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
            />
            <span className="text-sm text-muted-foreground">°C</span>
            <button
              onMouseDown={(e) => e.preventDefault()}
              onClick={applyTempTarget}
              className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20"
            >
              Apply
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => tempToggle(true)}
              className={`px-4 py-2.5 rounded-lg font-medium transition-all shadow-md ${
                tempEnabled
                  ? "bg-success text-success-foreground shadow-success/20"
                  : "bg-secondary text-secondary-foreground hover:bg-muted"
              }`}
            >
              Peltier ON
            </button>
            <button
              onClick={() => tempToggle(false)}
              className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
            >
              Peltier OFF
            </button>
          </div>
          {tempError && <div className="text-xs text-destructive font-semibold">{tempError}</div>}
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Flow Meter</h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Flow</span>
              <span className="text-foreground font-semibold">{flowMlMin.toFixed(2)} mL/min</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total</span>
              <span className="text-foreground font-semibold">{totalMl.toFixed(1)} mL</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Reading</span>
              <span className={flowRunning ? "text-success font-semibold" : "text-muted-foreground"}>
                {flowRunning ? "ON" : "OFF"}
              </span>
            </div>
          </div>
          <div className="pt-2">
            <label className="text-sm text-muted-foreground block mb-2">Target Volume (mL)</label>
            <input
              type="number"
              value={targetVolumeMl}
              onChange={(e) => setTargetVolumeMl(Math.max(0, Number.parseFloat(e.target.value) || 0))}
              min="0"
              step="0.1"
              className="w-28 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
            />
          </div>
          <div className="grid grid-cols-3 gap-3 pt-2">
            <button
              onClick={flowStart}
              className="px-4 py-2.5 bg-success text-success-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-success/20"
            >
              Start
            </button>
            <button
              onClick={flowStop}
              className="px-4 py-2.5 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-muted transition-all shadow-md"
            >
              Stop
            </button>
            <button
              onClick={flowReset}
              className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
            >
              Reset
            </button>
          </div>
          {flowError && <div className="text-xs text-destructive font-semibold">{flowError}</div>}
        </div>
      </div>
    </div>
  )
}
