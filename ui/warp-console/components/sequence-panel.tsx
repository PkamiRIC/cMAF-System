"use client"

import type { DeviceStatus } from "./status-display"

interface SequencePanelProps {
  activeSequence: "seq1" | "seq2" | "clean" | null
  setActiveSequence: (seq: "seq1" | "seq2" | "clean") => void
  status?: DeviceStatus
  error?: string | null
}

export default function SequencePanel({ activeSequence, setActiveSequence, status, error }: SequencePanelProps) {
  return (
    <div className="premium-card p-6 space-y-4">
      <h2 className="text-lg font-semibold text-foreground">Sequences</h2>

      <div className="flex gap-3">
        <button
          onClick={() => setActiveSequence("seq1")}
          className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-all shadow-md ${
            activeSequence === "seq1"
              ? "bg-primary text-primary-foreground shadow-primary/20"
              : "bg-secondary text-secondary-foreground hover:bg-muted"
          }`}
        >
          Sequence 1
        </button>
        <button
          onClick={() => setActiveSequence("seq2")}
          className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-all shadow-md ${
            activeSequence === "seq2"
              ? "bg-primary text-primary-foreground shadow-primary/20"
              : "bg-secondary text-secondary-foreground hover:bg-muted"
          }`}
        >
          Sequence 2
        </button>
        <button
          onClick={() => setActiveSequence("clean")}
          className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-all shadow-md ${
            activeSequence === "clean"
              ? "bg-primary text-primary-foreground shadow-primary/20"
              : "bg-secondary text-secondary-foreground hover:bg-muted"
          }`}
        >
          Cleaning
        </button>
      </div>

      <div className="mt-4 p-4 bg-secondary/50 backdrop-blur-sm border border-border rounded-lg space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground font-medium">Active:</span>
          <span className="text-sm text-foreground font-semibold">
            {activeSequence === "seq1"
              ? "Sequence 1"
              : activeSequence === "seq2"
              ? "Sequence 2"
              : activeSequence === "clean"
              ? "Cleaning"
              : "None"}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground font-medium">Status:</span>
          <span className="text-sm font-semibold flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                status?.state === "RUNNING" ? "bg-primary animate-pulse shadow-lg shadow-primary/50" : "bg-muted"
              }`}
            />
            {status?.state || "unknown"}
          </span>
        </div>
        {status?.sequence_step && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground font-medium">Step:</span>
            <span className="text-sm text-foreground font-semibold">{status.sequence_step}</span>
          </div>
        )}
        {status?.last_error && (
          <div className="text-xs text-destructive font-semibold">Error: {status.last_error}</div>
        )}
        {error && <div className="text-xs text-destructive font-semibold">UI error: {error}</div>}
      </div>
    </div>
  )
}
