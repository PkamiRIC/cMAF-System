import argparse
import sys
from pathlib import Path

import uvicorn

# Ensure the src package is first on sys.path so we import the updated modules
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from infra.config import load_config, DeviceConfig
from interfaces.api import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WARP Device backend")
    parser.add_argument(
        "--config",
        type=str,
        default="config/device2.yaml",
        help="Path to YAML configuration file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load configuration (returns DeviceConfig)
    cfg: DeviceConfig = load_config(args.config)

    # Build FastAPI app
    app = create_app(config=cfg, config_path=args.config)

    # Run Uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=cfg.network.api_port,
    )


if __name__ == "__main__":
    main()
