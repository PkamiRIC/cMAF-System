"use client"

import { useState } from "react"
import AxisWidget from "./axis-widget"
import SyringeWidget from "./syringe-widget"

export default function ControlPanel() {
  const [verticalPos, setVerticalPos] = useState(25.0)
  const [verticalTarget, setVerticalTarget] = useState(50.0)
  const [verticalVelocity, setVerticalVelocity] = useState(40.0)
  const [verticalHomed, setVerticalHomed] = useState(true)
  const [verticalEnabled, setVerticalEnabled] = useState(true)
  const [verticalFault, setVerticalFault] = useState(false)
  const [verticalPosition, setVerticalPosition] = useState(50.0)
  const [verticalSpeed, setVerticalSpeed] = useState(5.0)

  const [horizontalPos, setHorizontalPos] = useState(60.0)
  const [horizontalTarget, setHorizontalTarget] = useState(100.0)
  const [horizontalVelocity, setHorizontalVelocity] = useState(60.0)
  const [horizontalHomed, setHorizontalHomed] = useState(true)
  const [horizontalEnabled, setHorizontalEnabled] = useState(true)
  const [horizontalFault, setHorizontalFault] = useState(false)
  const [horizontalPosition, setHorizontalPosition] = useState(100.0)
  const [horizontalSpeed, setHorizontalSpeed] = useState(5.0)

  const [syringeVolume, setSyringeVolume] = useState(2.5)
  const [flowRate, setFlowRate] = useState(1.0)
  const [isSyringeActive, setIsSyringeActive] = useState(false)

  const [relayStates, setRelayStates] = useState<boolean[]>(Array(8).fill(false))

  const toggleRelay = (index: number) => {
    const newStates = [...relayStates]
    newStates[index] = !newStates[index]
    setRelayStates(newStates)
  }

  const toggleAllRelays = (state: boolean) => {
    setRelayStates(Array(8).fill(state))
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AxisWidget
          axisId="Z"
          name="Vertical Axis – Device 3"
          orientation="vertical"
          positionMm={verticalPos}
          minMm={0}
          maxMm={200}
          targetMm={verticalTarget}
          velocityMmPerS={verticalVelocity}
          homed={verticalHomed}
          enabled={verticalEnabled}
          fault={verticalFault}
          onPosition1={() => setVerticalPos(50)}
          onPosition2={() => setVerticalPos(100)}
          onPosition3={() => setVerticalPos(150)}
          onHome={() => setVerticalPos(0)}
          position={verticalPosition}
          speed={verticalSpeed}
          onPositionChange={setVerticalPosition}
          onSpeedChange={setVerticalSpeed}
        />

        <AxisWidget
          axisId="X"
          name="Horizontal Axis – Device 3"
          orientation="horizontal"
          positionMm={horizontalPos}
          minMm={0}
          maxMm={300}
          targetMm={horizontalTarget}
          velocityMmPerS={horizontalVelocity}
          homed={horizontalHomed}
          enabled={horizontalEnabled}
          fault={horizontalFault}
          onPosition1={() => setHorizontalPos(100)}
          onPosition2={() => setHorizontalPos(200)}
          onPosition3={() => setHorizontalPos(280)}
          onHome={() => setHorizontalPos(0)}
          position={horizontalPosition}
          speed={horizontalSpeed}
          onPositionChange={setHorizontalPosition}
          onSpeedChange={setHorizontalSpeed}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="premium-card p-6 flex items-center justify-center">
          <SyringeWidget volume={syringeVolume} maxVolume={10} isActive={isSyringeActive} />
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Syringe Control</h2>
          <p className="text-sm text-muted-foreground">
            Status:{" "}
            <span className={isSyringeActive ? "text-success font-medium" : "text-muted-foreground"}>
              {isSyringeActive ? "Active" : "Idle"}
            </span>
          </p>

          <div className="space-y-3">
            <div>
              <label className="text-sm text-muted-foreground block mb-2">Volume (mL)</label>
              <input
                type="number"
                value={syringeVolume}
                onChange={(e) => setSyringeVolume(Math.min(10, Math.max(0, Number.parseFloat(e.target.value) || 0)))}
                min="0"
                max="10"
                step="0.1"
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground block mb-2">Flow Rate (mL/min)</label>
              <input
                type="number"
                value={flowRate}
                onChange={(e) => setFlowRate(Number.parseFloat(e.target.value) || 0)}
                min="0"
                step="0.1"
                className="w-24 px-3 py-2 bg-input border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button className="flex-1 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-primary/20">
                Draw
              </button>
              <button
                onClick={() => setIsSyringeActive(!isSyringeActive)}
                className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all shadow-md ${
                  isSyringeActive
                    ? "bg-destructive text-destructive-foreground hover:opacity-90 shadow-destructive/20"
                    : "bg-primary text-primary-foreground hover:opacity-90 shadow-primary/20"
                }`}
              >
                {isSyringeActive ? "Stop" : "Dispense"}
              </button>
            </div>
          </div>
        </div>

        <div className="premium-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Relays</h2>

          <div className="grid grid-cols-4 gap-3">
            {relayStates.map((isActive, index) => (
              <button
                key={`relay-${index}`}
                onClick={() => toggleRelay(index)}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-all shadow-md ${
                  isActive
                    ? "bg-primary text-primary-foreground hover:opacity-90 shadow-primary/20"
                    : "bg-secondary text-secondary-foreground hover:bg-muted"
                }`}
              >
                R{index + 1}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <button
              onClick={() => toggleAllRelays(true)}
              className="px-4 py-2.5 bg-success text-success-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-success/20"
            >
              All ON
            </button>
            <button
              onClick={() => toggleAllRelays(false)}
              className="px-4 py-2.5 bg-destructive text-destructive-foreground rounded-lg font-medium hover:opacity-90 transition-all shadow-md shadow-destructive/20"
            >
              All OFF
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
