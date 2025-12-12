"use client"

import { useState } from "react"
import RotaryValveWidget from "./rotary-valve-widget"
import SequencePanel from "./sequence-panel"

export default function StatusDisplay() {
  const [activeSequence, setActiveSequence] = useState<"seq1" | "seq2" | "seq3">("seq1")

  const handleInitialize = () => {
    console.log("[v0] Initialize system")
  }

  const handleStop = () => {
    console.log("[v0] Stop all operations")
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6">
      {/* Rotary Valve */}
      <RotaryValveWidget />

      <div className="flex flex-col gap-6 h-full">
        <SequencePanel activeSequence={activeSequence} setActiveSequence={setActiveSequence} />

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
          </div>
        </div>
      </div>
    </div>
  )
}
