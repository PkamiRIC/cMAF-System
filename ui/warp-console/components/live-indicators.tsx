"use client"

import { useEffect, useState } from "react"
import type { DeviceStatus } from "./status-display"
import { getApiBase } from "../lib/api-base"

const apiBase = getApiBase()

async function fetchStatus(): Promise<DeviceStatus> {
  const res = await fetch(`${apiBase}/status`, { cache: "no-store" })
  if (!res.ok) throw new Error(`status failed (${res.status})`)
  return res.json()
}

function boolLabel(value: boolean | null | undefined, onLabel = "ON", offLabel = "OFF") {
  if (value === null || value === undefined) return "N/A"
  return value ? onLabel : offLabel
}

export default function LiveIndicators() {
  const [status, setStatus] = useState<DeviceStatus>({})
  const [error, setError] = useState<string | null>(null)

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
    const id = setInterval(tick, 1000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const groupedIndicators = [
    {
      title: "Sequence",
      items: [
        { label: "Controller", value: status.state || "unknown" },
        { label: "Current", value: status.current_sequence || "None" },
        { label: "Step", value: status.sequence_step || "N/A" },
      ],
    },
    {
      title: "Axes & Syringe",
      items: [
        { label: "X Homed", value: boolLabel(status.x_homed) },
        { label: "Z Homed", value: boolLabel(status.z_homed) },
        { label: "Syringe Homed", value: boolLabel(status.syringe_homed) },
        { label: "Syringe Busy", value: boolLabel(status.syringe_busy) },
        {
          label: "Syringe Volume",
          value:
            typeof status.syringe_volume_ml === "number" ? `${status.syringe_volume_ml.toFixed(2)} mL` : "N/A",
        },
      ],
    },
    {
      title: "Flow",
      items: [
        {
          label: "Rate",
          value: typeof status.flow_ml_min === "number" ? `${status.flow_ml_min.toFixed(2)} mL/min` : "N/A",
        },
        { label: "Reader", value: boolLabel(status.flow_running) },
        {
          label: "Total",
          value: typeof status.total_ml === "number" ? `${status.total_ml.toFixed(1)} mL` : "N/A",
        },
      ],
    },
    {
      title: "Temperature & Control",
      items: [
        {
          label: "Current",
          value: typeof status.temp_current_c === "number" ? `${status.temp_current_c.toFixed(2)} C` : "N/A",
        },
        {
          label: "Target",
          value: typeof status.temp_target_c === "number" ? `${status.temp_target_c.toFixed(1)} C` : "N/A",
        },
        { label: "Ready", value: boolLabel(status.temp_ready) },
        { label: "Peristaltic", value: boolLabel(status.peristaltic_enabled) },
        { label: "PID", value: boolLabel(status.pid_enabled) },
      ],
    },
  ]

  return (
    <div className="premium-card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Live Indicators</h2>
        <span className="text-xs text-muted-foreground">1s refresh</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {groupedIndicators.map((group) => (
          <div key={group.title} className="p-3 rounded-lg border border-border bg-secondary/30 space-y-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">{group.title}</p>
            <div className="space-y-1.5">
              {group.items.map((item) => (
                <div key={`${group.title}-${item.label}`} className="flex items-center justify-between gap-3">
                  <span className="text-xs text-muted-foreground">{item.label}</span>
                  <span className="text-xs font-semibold text-foreground text-right">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {error && <div className="text-xs text-destructive">{error}</div>}
    </div>
  )
}
