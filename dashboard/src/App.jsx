import { DeviceCard } from "./components/DeviceCard";

function App() {
  const device3Url = "http://warp3plc.local:8003";

  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <h1 className="text-3xl font-bold mb-6">WARP Dashboard</h1>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <DeviceCard name="Device 3 (WARP3PLC)" baseUrl={device3Url} />
      </div>
    </div>
  );
}

export default App;
