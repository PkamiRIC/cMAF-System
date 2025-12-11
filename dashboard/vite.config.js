import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/status": "http://warp3plc.local:8003",
      "/events": "http://warp3plc.local:8003",
      "/command": "http://warp3plc.local:8003",
      "/relays": "http://warp3plc.local:8003",
      "/rotary": "http://warp3plc.local:8003",
      "/syringe": "http://warp3plc.local:8003",
    },
  },
});
