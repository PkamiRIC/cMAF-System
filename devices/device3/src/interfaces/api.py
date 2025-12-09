from fastapi import FastAPI
from ..domain.controller import DeviceController
from ..domain.models import DeviceStatus

def create_app(controller: DeviceController) -> FastAPI:
    app = FastAPI()

    @app.get("/status", response_model=DeviceStatus)
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
