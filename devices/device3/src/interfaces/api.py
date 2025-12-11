from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from domain.controller import DeviceController
from infra.config import DeviceConfig


class SyringeMove(BaseModel):
    volume_ml: float = Field(..., description="Absolute target volume in mL")
    flow_ml_min: float = Field(..., description="Flow rate in mL/min")


def create_app(config: DeviceConfig, config_path: str):
    controller = DeviceController(config)

    app = FastAPI()

    @app.get("/status")
    def status():
        return controller.get_status()

    @app.post("/command/start/{sequence_name}")
    def start(sequence_name: str):
        try:
            controller.start_sequence(sequence_name)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/command/stop")
    def stop():
        controller.stop_sequence()
        return {"ok": True}

    @app.post("/command/home")
    def home():
        controller.home_all()
        return {"ok": True}

    @app.post("/command/emergency_stop")
    def emergency():
        controller.emergency_stop()
        return {"ok": True}

    @app.post("/relays/{channel}/{state}")
    def relay(channel: int, state: Literal["on", "off"]):
        try:
            ok = controller.set_relay(channel, state == "on")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": ok}

    @app.post("/rotary/{port}")
    def rotary(port: int):
        try:
            ok = controller.set_rotary_port(port)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": ok}

    @app.post("/syringe/move")
    def syringe_move(payload: SyringeMove):
        try:
            controller.move_syringe(payload.volume_ml, payload.flow_ml_min)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    return app
