"use client"

import { useState } from "react"
import { Lock } from "lucide-react"
import Header from "./header"
import ControlPanel from "./control-panel"
import StatusDisplay from "./status-display"
import EventLog from "./event-log"
import LiveIndicators from "./live-indicators"
import { getApiBase } from "../lib/api-base"

const apiBase = getApiBase()

export default function Dashboard() {
  const [targetVolumeMl, setTargetVolumeMl] = useState(50)
  const [sequenceTempTargetDraft, setSequenceTempTargetDraft] = useState("")
  const [activeTab, setActiveTab] = useState<"operations" | "advanced">("operations")
  const [advancedUnlocked, setAdvancedUnlocked] = useState(false)
  const [advancedPassword, setAdvancedPassword] = useState("")
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [unlocking, setUnlocking] = useState(false)

  const handleAdvancedTabClick = () => {
    setActiveTab("advanced")
    setPasswordError(null)
  }

  const handleUnlockAdvanced = async () => {
    if (!advancedPassword.trim()) {
      setPasswordError("Password is required")
      return
    }
    setUnlocking(true)
    try {
      const res = await fetch(`${apiBase}/auth/advanced/unlock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: advancedPassword }),
      })
      if (!res.ok) {
        let detail = "Unlock failed"
        try {
          const data = await res.json()
          if (data?.detail) detail = String(data.detail)
        } catch {}
        throw new Error(detail)
      }
      setAdvancedUnlocked(true)
      setPasswordError(null)
    } catch (err: any) {
      setPasswordError(err?.message || "Unlock failed")
    } finally {
      setUnlocking(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/30 p-6 space-y-6">
      <Header />

      <div className="space-y-6 animate-in fade-in duration-700">
        <div className="premium-card p-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              onClick={() => setActiveTab("operations")}
              className={`px-4 py-3 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "operations"
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : "bg-secondary text-secondary-foreground hover:bg-muted"
              }`}
            >
              Operations
            </button>
            <button
              onClick={handleAdvancedTabClick}
              className={`px-4 py-3 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2 ${
                activeTab === "advanced"
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : "bg-secondary text-secondary-foreground hover:bg-muted"
              }`}
            >
              <Lock className="w-4 h-4" />
              Advanced Controls
            </button>
          </div>
        </div>

        {activeTab === "operations" && (
          <div className="space-y-6">
            <StatusDisplay
              targetVolumeMl={targetVolumeMl}
              sequenceTempTargetDraft={sequenceTempTargetDraft}
            />
            <LiveIndicators />
            <EventLog />
          </div>
        )}

        {activeTab === "advanced" && !advancedUnlocked && (
          <div className="premium-card p-6 space-y-4 max-w-xl mx-auto">
            <h2 className="text-lg font-semibold text-foreground">Advanced Controls (Locked)</h2>
            <p className="text-sm text-muted-foreground">
              Enter password to access the full control interface.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="password"
                value={advancedPassword}
                onChange={(e) => setAdvancedPassword(e.target.value)}
                className="flex-1 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                placeholder="Password"
              />
              <button
                onClick={handleUnlockAdvanced}
                disabled={unlocking}
                className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20"
              >
                {unlocking ? "Unlocking..." : "Unlock"}
              </button>
            </div>
            {passwordError && <p className="text-xs text-destructive">{passwordError}</p>}
          </div>
        )}

        {activeTab === "advanced" && advancedUnlocked && (
          <div className="space-y-6">
            <ControlPanel
              targetVolumeMl={targetVolumeMl}
              setTargetVolumeMl={setTargetVolumeMl}
              setSequenceTempTargetDraft={setSequenceTempTargetDraft}
            />
            <StatusDisplay
              targetVolumeMl={targetVolumeMl}
              sequenceTempTargetDraft={sequenceTempTargetDraft}
            />
            <EventLog />
          </div>
        )}
      </div>
    </div>
  )
}
