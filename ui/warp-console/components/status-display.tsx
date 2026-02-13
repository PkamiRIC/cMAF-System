"use client";

import { useEffect, useMemo, useState } from "react"
import SequencePanel from "./sequence-panel"
import { getApiBase } from "../lib/api-base"

export type DeviceStatus = {
  state?: string
  current_sequence?: string | null
  sequence_step?: string | null
  last_error?: string | null
  syringe_busy?: boolean
  syringe_volume_ml?: number | null
  relay_states?: Record<string, boolean> // or Record<number, boolean>
  x_homed?: boolean
  z_homed?: boolean
  syringe_homed?: boolean
  peristaltic_enabled?: boolean
  peristaltic_direction_cw?: boolean
  peristaltic_low_speed?: boolean
  pid_enabled?: boolean
  pid_setpoint?: number
  pid_hall?: number | null
  flow_ml_min?: number
  total_ml?: number
  flow_running?: boolean
  flow_error?: string | null
  temp_enabled?: boolean
  temp_ready?: boolean | null
  temp_target_c?: number
  temp_current_c?: number | null
  temp_error?: string | null
  target_volume_ml?: number | null
}

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

type StatusDisplayProps = {
  targetVolumeMl: number
  sequenceTempTargetDraft: string
}

export default function StatusDisplay({
  targetVolumeMl,
  sequenceTempTargetDraft,
}: StatusDisplayProps) {
  const [status, setStatus] = useState<DeviceStatus>({})
  const [error, setError] = useState<string | null>(null)
  const activeSequence = useMemo<"seq1" | "seq2" | "clean" | null>(() => {
    if (status.current_sequence?.toLowerCase().includes("2")) return "seq2"
    if (status.current_sequence?.toLowerCase().includes("clean")) return "clean"
    if (status.current_sequence?.toLowerCase().includes("1")) return "seq1"
    return null
  }, [status.current_sequence])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const data = await fetchStatus()
        if (!cancelled) {
          setStatus(data)
          setError(null)
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message || "Status error")
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const handleInitialize = async () => {
    try {
      await post("/command/home")
    } catch (err: any) {
      setError(err?.message || "Init failed")
    }
  }

  const handleStop = async () => {
    try {
      await post("/command/emergency_stop")
    } catch (err: any) {
      setError(err?.message || "Stop failed")
    }
  }

  const handleStartSequence = async (seq: "seq1" | "seq2" | "clean") => {
    const name = seq === "seq2" ? "sequence2" : seq === "clean" ? "cleaning" : "sequence1"
    try {
      const trimmed = sequenceTempTargetDraft.trim()
      const parsed = trimmed.length > 0 ? Number.parseFloat(trimmed) : NaN
      const tempTargetPayload = Number.isFinite(parsed) ? { temp_target_c: parsed } : {}
      const payload =
        seq === "seq1"
          ? { target_volume_ml: targetVolumeMl, ...tempTargetPayload }
          : { ...tempTargetPayload }
      await post(`/command/start/${name}`, payload)
    } catch (err: any) {
      setError(err?.message || "Start failed")
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6">
      <SequencePanel
        activeSequence={activeSequence}
        setActiveSequence={handleStartSequence}
        status={status}
        error={error}
      />

      {/* System Controls Panel */}
      <div className="premium-card p-6 flex flex-col justify-center">
        <h2 className="text-lg font-semibold text-foreground mb-6">System Controls</h2>
        <div className="space-y-4">
          <button
            onClick={handleInitialize}
            className="w-full px-6 py-4 bg-success text-success-foreground rounded-xl font-semibold hover:opacity-90 transition-all shadow-lg shadow-success/20"
          >
            Initialize
          </button>
          <button
            onClick={handleStop}
            className="w-full px-6 py-4 bg-destructive text-destructive-foreground rounded-xl font-semibold hover:opacity-90 transition-all shadow-lg shadow-destructive/20"
          >
            STOP ALL
          </button>
          {error && <p className="text-xs text-destructive mt-2">{error}</p>}
        </div>
      </div>
    </div>
  )
}
