#!/usr/bin/env python3
"""
Standalone CLI for Sensirion SLF3S-1300F via SCC1-USB bridge.

Features:
- Continuous measurement loop
- Interactive start/stop/quit commands
- 20 ms polling by default
"""

import argparse
import sys
import threading
import time
from typing import Optional

try:
    from slf3s_usb_sensor import SLF3SUSBFlowSensor
except ModuleNotFoundError as exc:
    if exc.name == "serial":
        print("Missing dependency: pyserial")
        print("Install with: py -3 -m pip install pyserial")
        sys.exit(1)
    raise

from serial import SerialException
from serial.tools import list_ports


class CommandState:
    def __init__(self) -> None:
        self.running = False
        self.shutdown = False
        self.lock = threading.Lock()

    def set_running(self, value: bool) -> None:
        with self.lock:
            self.running = value

    def is_running(self) -> bool:
        with self.lock:
            return self.running

    def request_shutdown(self) -> None:
        with self.lock:
            self.shutdown = True

    def is_shutdown(self) -> bool:
        with self.lock:
            return self.shutdown


def input_worker(state: CommandState) -> None:
    print("Commands: start | stop | quit")
    while not state.is_shutdown():
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            state.request_shutdown()
            return

        if cmd == "start":
            state.set_running(True)
            print("Measurement started")
        elif cmd == "stop":
            state.set_running(False)
            print("Measurement stopped")
        elif cmd in ("quit", "exit", "q"):
            state.request_shutdown()
            return
        elif cmd == "":
            continue
        else:
            print("Unknown command. Use: start | stop | quit")


def run(
    port: str,
    baudrate: int,
    medium: str,
    interval_ms: int,
    scale_factor: Optional[float],
) -> None:
    state = CommandState()
    try:
        sensor = SLF3SUSBFlowSensor(
            port=port,
            baudrate=baudrate,
            medium=medium,
            interval_ms=interval_ms,
            scale_factor=scale_factor,
            auto_start=False,
        )
    except SerialException as exc:
        print(f"Failed to open port {port}: {exc}")
        print("Likely causes:")
        print("1) Another app is already using this COM port")
        print("2) Wrong COM port selected")
        print("3) Device was unplugged/re-enumerated")
        print("")
        print("Use --list-ports to see available ports.")
        return

    thread = threading.Thread(target=input_worker, args=(state,), daemon=True)
    thread.start()

    with sensor:
        print(
            f"Connected on {port} @ {baudrate}. "
            f"Polling every {interval_ms} ms."
        )
        print("Type 'start' to begin streaming.")

        next_deadline = time.perf_counter()
        active = False

        while not state.is_shutdown():
            should_run = state.is_running()

            if should_run and not active:
                sensor.start(interval_ms=interval_ms)
                sensor.reset_totals()
                active = True
                next_deadline = time.perf_counter()
            elif not should_run and active:
                sensor.stop()
                active = False
                time.sleep(0.02)
                continue

            if not active:
                time.sleep(0.05)
                continue

            data = sensor.read()
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"{ts} | flow={data['flow_ml_min']:9.3f} mL/min | "
                f"total={data['total_ml']:10.3f} mL"
            )

            next_deadline += interval_ms / 1000.0
            sleep_for = next_deadline - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_deadline = time.perf_counter()

        if active:
            sensor.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone SLF3S-1300F live reader (start/stop, 20 ms polling)."
    )
    parser.add_argument("--port", help="COM port, e.g. COM5")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--medium", default="water", choices=["water", "ipa"])
    parser.add_argument("--interval-ms", type=int, default=10)
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=None,
        help="Optional manual scale factor (ticks per mL/min).",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List detected serial ports and exit.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.list_ports:
        ports = list(list_ports.comports())
        if not ports:
            print("No serial ports detected.")
            sys.exit(0)
        print("Detected serial ports:")
        for p in ports:
            desc = p.description or "Unknown device"
            hwid = p.hwid or ""
            print(f"- {p.device}: {desc} {hwid}".rstrip())
        sys.exit(0)
    if not args.port:
        print("Error: --port is required unless --list-ports is used.")
        sys.exit(2)
    run(
        port=args.port,
        baudrate=args.baudrate,
        medium=args.medium,
        interval_ms=args.interval_ms,
        scale_factor=args.scale_factor,
    )
