import ThemeToggle from "./theme-toggle"
import { Activity } from "lucide-react"

export default function Header() {
  return (
    <header className="premium-card p-6 backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
            <span className="text-2xl font-bold text-primary-foreground">W</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              cMAF Device 2
            </h1>
            <p className="text-sm text-muted-foreground font-medium">cMAF Control System</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 px-6 py-3 rounded-xl bg-success/10 border border-success/20">
            <Activity className="w-5 h-5 text-success animate-pulse" />
            <div>
              <p className="text-xs text-muted-foreground font-medium">System Status</p>
              <p className="text-sm font-semibold text-success">Operational</p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
