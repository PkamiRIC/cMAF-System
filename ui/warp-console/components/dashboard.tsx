"use client"

import Header from "./header"
import ControlPanel from "./control-panel"
import StatusDisplay from "./status-display"
import EventLog from "./event-log"

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/30 p-6 space-y-6">
      <Header />

      <div className="space-y-6 animate-in fade-in duration-700">
        {/* Row 1: Axis Controls and Syringe */}
        <ControlPanel />

        {/* Row 2: Sequences and System Controls */}
        <StatusDisplay />

        {/* Row 3: Event Log */}
        <EventLog />
      </div>
    </div>
  )
}
