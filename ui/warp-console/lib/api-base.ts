const FALLBACK_API_BASE = "http://warp2plc.local:8002"

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8002`
  }
  return FALLBACK_API_BASE
}
