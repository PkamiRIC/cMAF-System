from typing import Optional

from pydantic import BaseModel

class DeviceStatus(BaseModel):
    device_id: str
    state: str  # "IDLE", "RUNNING", "ERROR"
    current_sequence: Optional[str]
    sequence_step: Optional[str]
    last_error: Optional[str]
    pressure_bar: float
    flow_lpm: float
    total_volume_l: float
    stop_requested: bool
