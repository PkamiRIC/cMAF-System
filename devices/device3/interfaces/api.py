from fastapi import FastAPI
from typing import Optional

from infra.config import DeviceConfig, load_config
from domain.controller import DeviceController


def _build_controller(config: Optional[DeviceConfig], config_path: Optional[str]) -> DeviceConfig:
    """
    Helper to ensure we always end up with a DeviceConfig, regardless of
    whether main() passes an object or a path.
    """
    if config is not None:
        return config

    # Fallback to loading from a path (or defaults)
    return load_config(config_path)


def create_app(
    config: Optional[DeviceConfig] = None,
    config_path: Optional[str] = None,
) -> FastAPI:
    """
    Factory to create the FastAPI app.

    This is intentionally flexible so that main.py can either:
    - call create_app(config=DeviceConfig(...)), or
    - call create_app(config_path="config/device3.yaml"), or
    - call create_app() and let defaults apply.
    """
    resolved_config = _build_controller(config, config_path)
    controller = DeviceController(resolved_config)

    app = FastAPI(title=f"WARP Device {resolved_config.device_id}")

    @app.get("/status")
    def get_status():
        return controller.get_status()

    @app.post("/command/start/{sequence_name}")
    def start_sequence(sequence_name: str):
        controller.start_sequence(sequence_name)
        return {"ok": True}

    @app.post("/command/emergency_stop")
    def emergency_stop():
        controller.emergency_stop()
        return {"ok": True}

    return app
