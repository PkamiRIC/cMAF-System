#!/usr/bin/env python3
import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relay test using legacy relay_board driver (DeviceGUI_v17)."
    )
    parser.add_argument("--port", default="/dev/ttySC3", help="Serial port (e.g. /dev/ttySC3)")
    parser.add_argument("--address", type=int, default=1, help="Relay board address (e.g. 1 or 2)")
    parser.add_argument("--relay", type=int, default=1, help="Relay number to toggle (1-8)")
    parser.add_argument("--on-ms", type=int, default=500, help="ON duration in ms")
    args = parser.parse_args()

    sys.path.insert(0, "/home/pi/cMAF-System")
    from device.Old_Codes import relay_board  # type: ignore

    rb = relay_board.RelayBoard06(args.port, address=args.address)
    print(f"Opening {args.port} address={args.address} relay={args.relay}")

    rb.on(args.relay)
    print("ON")
    time.sleep(args.on_ms / 1000.0)
    rb.off(args.relay)
    print("OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
