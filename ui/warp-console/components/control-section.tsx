import type React from "react"
interface ControlSectionProps {
  title: string
  children: React.ReactNode
}

export default function ControlSection({ title, children }: ControlSectionProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 space-y-4">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      {children}
    </div>
  )
}
