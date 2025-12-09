import argparse
import uvicorn

from infra.config import load_config
from domain.controller import DeviceController
from interfaces.api import create_app

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    return parser.parse_args()

def main():
    args = parse_args()
    cfg = load_config(args.config)

    controller = DeviceController(device_id=cfg["device_id"])
    app = create_app(controller)

    uvicorn.run(app, host="0.0.0.0", port=cfg["network"]["api_port"])

if __name__ == "__main__":
    main()
