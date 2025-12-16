"use client"

import { useState, useEffect } from "react"

interface SyringeWidgetProps {
  volume: number
  maxVolume?: number
  isActive?: boolean
}

export default function SyringeWidget({ volume, maxVolume = 2.5, isActive = false }: SyringeWidgetProps) {
  const [displayVolume, setDisplayVolume] = useState(volume)

  useEffect(() => {
    setDisplayVolume(volume)
  }, [volume])

  const percentage = (displayVolume / maxVolume) * 100

  return (
    <div className="w-full">
      <h3 className="text-lg font-semibold text-foreground mb-4">Syringe</h3>

      <div className="flex justify-center items-end gap-3 h-52">
        {/* Barrel */}
        <div className="flex flex-col gap-2">
          <div className="relative w-24 h-44 bg-secondary/50 backdrop-blur-sm border-2 border-border rounded-b-3xl rounded-t-lg overflow-hidden shadow-inner">
            {/* Liquid fill */}
            <div
              className={`absolute bottom-0 inset-x-0 transition-all duration-300 ${
                isActive
                  ? "bg-gradient-to-t from-primary to-accent animate-pulse shadow-lg shadow-primary/50"
                  : "bg-gradient-to-t from-primary/80 to-accent/80"
              }`}
              style={{ height: `${percentage}%` }}
            />

            {/* Measurement marks */}
            <div className="absolute inset-0 pointer-events-none">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="absolute left-2 right-2 border-t border-border/40"
                  style={{ top: `${(i + 1) * 20}%` }}
                />
              ))}
            </div>
          </div>

          {/* Needle tip */}
          <div className="flex justify-center">
            <div className="w-1.5 h-4 bg-muted-foreground rounded-b-full shadow-sm" />
          </div>
        </div>
      </div>

      <div className="mt-4 text-center">
        <div className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          {displayVolume.toFixed(2)} mL
        </div>
        <div className="text-sm text-muted-foreground mt-1 font-medium">Max: {maxVolume} mL</div>
      </div>

      {isActive && (
        <div className="mt-4 flex items-center justify-center gap-2 bg-success/15 border border-success/30 rounded-lg py-2 shadow-sm">
          <div className="w-2 h-2 bg-success rounded-full animate-pulse shadow-lg shadow-success/50" />
          <span className="text-sm text-success font-semibold">Active</span>
        </div>
      )}
    </div>
  )
}
