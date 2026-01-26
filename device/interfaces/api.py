import asyncio
import json
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from domain.controller import DeviceController
from infra.config import DeviceConfig, load_config


class SyringeMove(BaseModel):
    volume_ml: float = Field(..., description="Absolute target volume in mL")
    flow_ml_min: float = Field(..., description="Flow rate in mL/min")


def _build_controller(config: Optional[DeviceConfig], config_path: Optional[str]) -> DeviceConfig:
    if config is not None:
        return config
    return load_config(config_path)


def create_app(
    config: Optional[DeviceConfig] = None,
    config_path: Optional[str] = None,
) -> FastAPI:
    cfg = _build_controller(config, config_path)
    controller = DeviceController(cfg)

    app = FastAPI(title=f"WARP Device {cfg.device_id}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    controller.attach_event_loop(asyncio.get_event_loop())

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

    @app.get("/events/sse")
    async def sse():
        queue: asyncio.Queue = asyncio.Queue()
        controller._sse_subscribers.append(queue)
        await queue.put(json.dumps(controller.get_status()))

        async def event_generator():
            try:
                while True:
                    data = await queue.get()
                    yield f"data: {data}\n\n"
            finally:
                try:
                    controller._sse_subscribers.remove(queue)
                except ValueError:
                    pass

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app
