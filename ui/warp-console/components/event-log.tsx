"use client";

import { useEffect, useMemo, useRef, useState } from "react"
import { getApiBase } from "../lib/api-base"

type StatusPayload = {
  logs?: string[]
}

const apiBase = getApiBase()

async function fetchStatusLogs(): Promise<string[] | null> {
  try {
    const res = await fetch(`${apiBase}/status`, { cache: "no-store" })
    if (!res.ok) return null
    const data = (await res.json()) as StatusPayload
    return Array.isArray(data.logs) ? data.logs : null
  } catch {
    return null
  }
}

export default function EventLog() {
  const [events, setEvents] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const listRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll to the newest entry when logs change.
  useEffect(() => {
    const node = listRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [events.length])

  useEffect(() => {
    let es: EventSource | null = null
    let retry: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      es = new EventSource(`${apiBase}/events/sse`)
      es.onopen = () => {
        setConnected(true)
        setError(null)
      }
      es.onmessage = (ev) => {
        try {
          const payload: StatusPayload = JSON.parse(ev.data || "{}")
          if (Array.isArray(payload.logs)) {
            setEvents(payload.logs)
          }
        } catch {
          // ignore malformed frames
        }
      }
      es.onerror = () => {
        setConnected(false)
        es?.close()
        if (retry) clearTimeout(retry)
        retry = setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      setConnected(false)
      if (retry) clearTimeout(retry)
      es?.close()
    }
  }, [])

  // Poll status as a fallback to keep logs populated even if SSE misses a frame.
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      const logs = await fetchStatusLogs()
      if (!cancelled && Array.isArray(logs)) {
        setEvents(logs)
      }
    }
    tick()
    const id = setInterval(tick, 3000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const handleClear = async () => {
    setClearing(true)
    try {
      const res = await fetch(`${apiBase}/logs/clear`, { method: "POST" })
      if (!res.ok) throw new Error(`Clear failed (${res.status})`)
      setEvents([])
      setError(null)
    } catch (err: any) {
      setError(err?.message || "Unable to clear log")
    } finally {
      setClearing(false)
    }
  }

  const emptyState = useMemo(() => !events || events.length === 0, [events])

  return (
    <div className="premium-card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Event Log</h2>
        <span className={`text-xs ${connected ? "text-success" : "text-destructive"}`}>
          {connected ? "live" : "reconnecting..."}
        </span>
      </div>

      <div
        ref={listRef}
        className="space-y-2 h-72 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent"
      >
        {emptyState ? (
          <div className="text-sm text-muted-foreground italic">No events yet.</div>
        ) : (
          events.map((event, idx) => (
            <div
              key={`${event}-${idx}`}
              className="text-sm text-muted-foreground font-mono border-l-2 border-primary/50 pl-4 py-2 bg-secondary/30 rounded-r-lg hover:bg-secondary/50 transition-colors"
            >
              {event}
            </div>
          ))
        )}
      </div>

      {error && <div className="text-xs text-destructive">{error}</div>}

      <button
        onClick={handleClear}
        disabled={clearing}
        className="w-full px-4 py-3 bg-secondary text-secondary-foreground rounded-xl font-medium hover:bg-muted transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {clearing ? "Clearing..." : "Clear Log"}
      </button>
    </div>
  )
}
