export default function EventLog() {
  const events = [
    "Connected on /dev/ttyUSB0",
    "Vertical Axis Ready",
    "Horizontal Axis Ready",
    "Syringe control ready",
    "System initialized",
  ]

  return (
    <div className="premium-card p-6 space-y-4">
      <h2 className="text-lg font-semibold text-foreground">Event Log</h2>

      <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent">
        {events.map((event, idx) => (
          <div
            key={idx}
            className="text-sm text-muted-foreground font-mono border-l-2 border-primary/50 pl-4 py-2 bg-secondary/30 rounded-r-lg hover:bg-secondary/50 transition-colors"
          >
            <span className="text-primary font-semibold">[{new Date().toLocaleTimeString()}]</span> {event}
          </div>
        ))}
      </div>

      <button className="w-full px-4 py-3 bg-secondary text-secondary-foreground rounded-xl font-medium hover:bg-muted transition-all shadow-md">
        Clear Log
      </button>
    </div>
  )
}
