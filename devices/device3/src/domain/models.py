from pydantic import BaseModel
from typing import Optional

class DeviceStatus(BaseModel):
    device_id: str
    state: str                # "IDLE", "RUNNING", "ERROR"
    current_sequence: Optional[str]
    last_error: Optional[str]
    pressure_bar: float
    flow_lpm: float
    total_volume_l: float
