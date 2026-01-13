const FALLBACK_API_BASE = "http://warp3plc.local:8003"

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8003`
  }
  return FALLBACK_API_BASE
}
