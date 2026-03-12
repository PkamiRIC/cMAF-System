"use client"

import { useEffect, useState } from "react"
import ThemeToggle from "./theme-toggle"
import { Activity, AlertTriangle } from "lucide-react"
import { getApiBase } from "../lib/api-base"

type BackendStatus = {
  last_error?: string | null
}

const apiBase = getApiBase()

export default function Header() {
  const [backendState, setBackendState] = useState<{
    healthy: boolean
    label: string
    detail: string
  }>({
    healthy: false,
    label: "Checking",
    detail: "Waiting for backend response",
  })

  useEffect(() => {
    let cancelled = false

    const pollBackend = async () => {
      try {
        const res = await fetch(`${apiBase}/status`, { cache: "no-store" })
        if (!res.ok) {
          throw new Error(`Backend unavailable (${res.status})`)
        }

        const data: BackendStatus = await res.json()
        const lastError = data.last_error?.trim()

        if (!cancelled) {
          if (lastError) {
            setBackendState({
              healthy: false,
              label: "Error",
              detail: lastError,
            })
          } else {
            setBackendState({
              healthy: true,
              label: "Operational",
              detail: "Backend connected",
            })
          }
        }
      } catch (error: any) {
        if (!cancelled) {
          setBackendState({
            healthy: false,
            label: "Error",
            detail: error?.message || "Backend unreachable",
          })
        }
      }
    }

    pollBackend()
    const intervalId = window.setInterval(pollBackend, 5000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  return (
    <header className="premium-card p-6 backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
            <span className="text-2xl font-bold text-primary-foreground">W</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              cMAF Device 2
            </h1>
            <p className="text-sm text-muted-foreground font-medium">cMAF Control System</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div
            className={`flex items-center gap-3 px-6 py-3 rounded-xl border ${
              backendState.healthy
                ? "bg-success/10 border-success/20"
                : "bg-destructive/10 border-destructive/20"
            }`}
          >
            {backendState.healthy ? (
              <Activity className="w-5 h-5 text-success animate-pulse" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-destructive" />
            )}
            <div>
              <p className="text-xs text-muted-foreground font-medium">System Status</p>
              <p
                className={`text-sm font-semibold ${
                  backendState.healthy ? "text-success" : "text-destructive"
                }`}
              >
                {backendState.label}
              </p>
              <p className="text-xs text-muted-foreground">{backendState.detail}</p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
