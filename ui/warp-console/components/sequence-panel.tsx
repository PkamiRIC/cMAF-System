"use client"

interface SequencePanelProps {
  activeSequence: "seq1" | "seq2" | "seq3"
  setActiveSequence: (seq: "seq1" | "seq2" | "seq3") => void
}

export default function SequencePanel({ activeSequence, setActiveSequence }: SequencePanelProps) {
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
          onClick={() => setActiveSequence("seq3")}
          className={`flex-1 px-4 py-3 rounded-xl font-semibold transition-all shadow-md ${
            activeSequence === "seq3"
              ? "bg-primary text-primary-foreground shadow-primary/20"
              : "bg-secondary text-secondary-foreground hover:bg-muted"
          }`}
        >
          Sequence 3
        </button>
      </div>

      <div className="mt-4 p-4 bg-secondary/50 backdrop-blur-sm border border-border rounded-lg space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground font-medium">Active:</span>
          <span className="text-sm text-foreground font-semibold">
            {activeSequence === "seq1" ? "Sequence 1" : activeSequence === "seq2" ? "Sequence 2" : "Sequence 3"}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground font-medium">Status:</span>
          <span className="text-sm text-success font-semibold flex items-center gap-2">
            <span className="w-2 h-2 bg-success rounded-full animate-pulse shadow-lg shadow-success/50" />
            Ready
          </span>
        </div>
      </div>
    </div>
  )
}
