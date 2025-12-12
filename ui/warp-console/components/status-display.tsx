"use client"

import { useEffect, useMemo, useState } from "react"
import RotaryValveWidget from "./rotary-valve-widget"
import SequencePanel from "./sequence-panel"

export type DeviceStatus = {
  state?: string
  current_sequence?: string | null
  sequence_step?: string | null
  rotary_port?: number | null
  last_error?: string | null
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8003"

async function post(path: string) {
  const res = await fetch(`${apiBase}${path}`, { method: "POST" })
  if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`)
}

async function fetchStatus(): Promise<DeviceStatus> {
  const res = await fetch(`${apiBase}/status`)
  if (!res.ok) throw new Error(`status failed (${res.status})`)
  return res.json()
}

export default function StatusDisplay() {
  const [status, setStatus] = useState<DeviceStatus>({})
  const [error, setError] = useState<string | null>(null)
  const activeSequence = useMemo<"seq1" | "seq2" | "seq3">(() => {
    if (status.current_sequence?.toLowerCase().includes("2")) return "seq2"
    if (status.current_sequence?.toLowerCase().includes("3")) return "seq3"
    return "seq1"
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
      await post("/command/stop")
    } catch (err: any) {
      setError(err?.message || "Stop failed")
    }
  }

  const handleStartSequence = async (seq: "seq1" | "seq2" | "seq3") => {
    const name = seq === "seq2" ? "sequence2" : "sequence1"
    try {
      await post(`/command/start/${name}`)
    } catch (err: any) {
      setError(err?.message || "Start failed")
    }
  }

  const handleRotaryChange = async (port: number) => {
    try {
      await post(`/rotary/${port}`)
      setStatus((s) => ({ ...s, rotary_port: port }))
    } catch (err: any) {
      setError(err?.message || "Rotary failed")
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6">
      {/* Rotary Valve */}
      <RotaryValveWidget
        activePort={status.rotary_port || 1}
        onSelect={handleRotaryChange}
        locked={status.state === "RUNNING"}
      />

      <div className="flex flex-col gap-6 h-full">
        <SequencePanel
          activeSequence={activeSequence}
          setActiveSequence={handleStartSequence}
          status={status}
          error={error}
        />

        {/* System Controls Panel */}
        <div className="premium-card p-6 flex-1 flex flex-col justify-center">
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
    </div>
  )
}
