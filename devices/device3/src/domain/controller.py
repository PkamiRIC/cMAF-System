from .models import DeviceStatus

class DeviceController:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.state = "IDLE"
        self.current_sequence = None
        self.last_error = None

    def get_status(self) -> DeviceStatus:
        # Dummy values for now (will wire to real sensors later)
        return DeviceStatus(
            device_id=self.device_id,
            state=self.state,
            current_sequence=self.current_sequence,
            last_error=self.last_error,
            pressure_bar=0.0,
            flow_lpm=0.0,
            total_volume_l=0.0,
        )

    def start_sequence(self, name: str):
        self.current_sequence = name
        self.state = "RUNNING"

    def emergency_stop(self):
        self.state = "ERROR"
        self.last_error = "Emergency stop triggered"
