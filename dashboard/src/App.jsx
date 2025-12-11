// dashboard/src/App.jsx
import "./App.css";
import { DeviceCard } from "./components/DeviceCard";

function App() {
  const device3Url = import.meta.env.VITE_DEVICE3_URL || "";

  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-bold">WARP Devices Dashboard</h1>
          <p className="text-sm text-gray-600">
            Monitoring and control for WARP device backends.
          </p>
        </header>

        <div className="grid gap-4 md:grid-cols-2">
          <DeviceCard name="Device 3" baseUrl={device3Url} />
          {/* Later: add Device 1 + Device 2 cards here */}
        </div>
      </div>
    </div>
  );
}

export default App;
