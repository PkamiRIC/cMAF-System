import asyncio
import json
import secrets
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from domain.controller import DeviceController
from infra.config import DeviceConfig


class SyringeMove(BaseModel):
    volume_ml: float = Field(..., description="Absolute target volume in mL")
    flow_ml_min: float = Field(..., description="Flow rate in mL/min")


class AxisMove(BaseModel):
    position_mm: float
    rpm: float


class PeristalticEnable(BaseModel):
    enabled: bool


class PeristalticDirection(BaseModel):
    forward: bool


class PeristalticSpeed(BaseModel):
    low_speed: bool


class PidEnable(BaseModel):
    enabled: bool


class PidSetpoint(BaseModel):
    value: float


class TempEnable(BaseModel):
    enabled: bool


class TempTarget(BaseModel):
    value_c: float


class StartSequence(BaseModel):
    target_volume_ml: Optional[float] = None
    temp_target_c: Optional[float] = None


class AdvancedUnlockPayload(BaseModel):
    password: str = Field(..., min_length=1)


def create_app(config: DeviceConfig, config_path: str):
    controller = DeviceController(config)

    app = FastAPI()
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

    @app.post("/auth/advanced/unlock")
    def auth_advanced_unlock(payload: AdvancedUnlockPayload):
        expected = config.auth.advanced_controls_password
        if not expected:
            raise HTTPException(status_code=503, detail="Advanced controls password not configured")
        if not secrets.compare_digest(payload.password, expected):
            raise HTTPException(status_code=401, detail="Invalid password")
        return {"ok": True}

    @app.post("/command/start/{sequence_name}")
    def start(sequence_name: str, payload: Optional[StartSequence] = None):
        try:
            target_ml = payload.target_volume_ml if payload else None
            temp_target_c = payload.temp_target_c if payload else None
            controller.start_sequence(
                sequence_name,
                target_volume_ml=target_ml,
                temp_target_c=temp_target_c,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/command/stop")
    def stop():
        controller.stop_sequence()
        return {"ok": True}

    @app.post("/command/home")
    def home():
        try:
            controller.home_all()
            return {"ok": True}
        except RuntimeError as exc:
            if "motion busy" in str(exc).lower():
                raise HTTPException(status_code=409, detail=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/command/emergency_stop")
    def emergency():
        controller.emergency_stop()
        return {"ok": True}

    @app.post("/relays/all/{state}")
    def relays_all(state: Literal["on", "off"]):
        try:
            ok = controller.set_all_relays(state == "on")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": ok}

    @app.post("/relays/{channel:int}/{state}")
    def relay(channel: int, state: Literal["on", "off"]):
        try:
            ok = controller.set_relay(channel, state == "on")
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

    @app.post("/syringe/stop")
    def syringe_stop():
        try:
            controller.stop_syringe()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/syringe/home")
    def syringe_home():
        try:
            controller.home_syringe()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/logs/clear")
    def clear_logs():
        controller.clear_logs()
        return {"ok": True}

    @app.post("/axis/{axis}/move")
    def axis_move(axis: Literal["X", "Z", "x", "z"], payload: AxisMove):
        try:
            controller.move_axis(axis, payload.position_mm, payload.rpm)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/axis/{axis}/home")
    def axis_home(axis: Literal["X", "Z", "x", "z"]):
        try:
            controller.home_axis(axis)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/peristaltic/enable")
    def peristaltic_enable(payload: PeristalticEnable):
        try:
            controller.set_peristaltic_enabled(payload.enabled)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/peristaltic/direction")
    def peristaltic_direction(payload: PeristalticDirection):
        try:
            controller.set_peristaltic_direction(payload.forward)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/peristaltic/speed")
    def peristaltic_speed(payload: PeristalticSpeed):
        try:
            controller.set_peristaltic_speed(payload.low_speed)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/pid/enable")
    def pid_enable(payload: PidEnable):
        try:
            controller.set_pid_enabled(payload.enabled)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/pid/setpoint")
    def pid_setpoint(payload: PidSetpoint):
        try:
            controller.set_pid_setpoint(payload.value)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/pid/home")
    def pid_home():
        try:
            controller.pid_home()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/pid/close")
    def pid_close():
        try:
            controller.pid_close()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/flow/start")
    def flow_start():
        try:
            controller.flow_start()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/flow/stop")
    def flow_stop():
        try:
            controller.flow_stop()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/flow/reset")
    def flow_reset():
        try:
            controller.flow_reset()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/temperature/enable")
    def temp_enable(payload: TempEnable):
        try:
            controller.set_temp_enabled(payload.enabled)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/temperature/target")
    def temp_target(payload: TempTarget):
        try:
            controller.set_temp_target(payload.value_c)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.get("/events/sse")
    async def sse():
        queue: asyncio.Queue = asyncio.Queue()
        controller._sse_subscribers.append(queue)
        # push initial status
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
