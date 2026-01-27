# maf_sequence.py
from typing import Callable, Optional

from sleeper import InterruptibleSleeper

"""
python3 slf3s_usb_test.py --port /dev/ttyUSB0 --interval 20 --sleep 0.25
to test the flow meter reading independently
"""

def run_maf_sequence(
    *,
    stop_flag: Callable[[], bool],
    reset_flow_and_timer: Callable[[], None],
    get_total_volume_ml: Callable[[], float],
    log: Optional[Callable[[str], None]] = None,
    relays=None,
    motor_pump=None,
    pid_controller=None,
    valve1=None,
    valve2=None,
    syringe=None,
    enable_temp_controller: Optional[Callable[[], None]] = None,
    disable_temp_controller: Optional[Callable[[], None]] = None,
    wait_for_temp_ready: Optional[Callable[[], None]] = None,
    wait_for_maf_heating: Optional[Callable[[], None]] = None,
    move_horizontal_to_filtering: Optional[Callable[[], None]] = None,
    move_horizontal_to_waste: Optional[Callable[[], None]] = None,
    move_horizontal_to_home: Optional[Callable[[], None]] = None,
    move_vertical_close_plate: Optional[Callable[[], None]] = None,
    move_vertical_open_plate: Optional[Callable[[], None]] = None,
    target_volume_ml: float = 50.0,
    post_volume_wait_s: float = 2.0,
    before_step: Optional[Callable[[str], None]] = None,
):
    """
    MAF full processing sequence (steps 1–36).

    The caller runs this in a worker thread; the function blocks while respecting
    the STOP flag via InterruptibleSleeper so the UI can interrupt safely.
    """

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    sleeper = InterruptibleSleeper(stop_flag)

    def check_stop() -> bool:
        """Return True if we should abort; also put hardware in a safe state."""
        if not stop_flag():
            return False

        _log("[INFO] MAF sequence aborted by STOP.")
        try:
            motor_pump.set_enabled(False)
            motor_pump.set_direction(False)
            motor_pump.set_speed_checked(False)
        except Exception:
            pass

        try:
            pid_controller.set_enabled(False)
        except Exception:
            pass

        if relays:
            try:
                relays.on(1)  # Valve 1 open
            except Exception:
                pass
            try:
                relays.on(2)  # Valve 2 open
            except Exception:
                pass

        return True

    MIN_STEP_DELAY = 0.5

    class SequenceAbort(Exception):
        """Internal signal used to unwind the sequence safely."""

    def _wait_block(duration: float):
        duration = max(duration, 0.0)
        if duration == 0.0:
            return
        try:
            sleeper.sleep(duration)
        except InterruptedError:
            check_stop()
            raise SequenceAbort

    def _run_step(
        step_label: str,
        action: Optional[Callable[[], None]] = None,
        wait_after: float = MIN_STEP_DELAY,
    ):
        if before_step:
            try:
                before_step(step_label)
            except InterruptedError:
                check_stop()
                raise SequenceAbort
            except Exception as exc:
                _log(f"[WARN] Step prompt failed ({step_label}): {exc}")
        if check_stop():
            raise SequenceAbort
        _log(step_label)
        success = True
        if action:
            try:
                action()
            except SequenceAbort:
                raise
            except InterruptedError:
                check_stop()
                raise SequenceAbort
            except Exception as exc:
                success = False
                _log(f"[WARN] {step_label} failed: {exc}")
        if success:
            _log(f"{step_label} completed")
        _wait_block(max(wait_after, MIN_STEP_DELAY))

    def _volume_loop():
        while True:
            if stop_flag():
                check_stop()
                raise SequenceAbort
            try:
                total = float(get_total_volume_ml())
            except Exception:
                total = 0.0
            _log(f"  [Flow] Total volume = {total:.2f} mL")
            if total >= target_volume_ml:
                break
            _wait_block(0.2)

    def _enable_peristaltic():
        motor_pump.set_direction(True)
        motor_pump.set_speed_checked(True)
        motor_pump.set_enabled(True)

    def _disable_peristaltic():
        motor_pump.set_enabled(False)
        motor_pump.set_direction(False)
        motor_pump.set_speed_checked(False)

    def _syringe_move(target_ml: float, flow_ml_min: float):
        if syringe is None:
            raise RuntimeError("Syringe adapter unavailable")
        syringe.goto_absolute(target_ml, flow_ml_min)

    _log("=== MAF sequence start ===")

    try:
        _run_step("Step 1: Initialization", reset_flow_totals)
       # _run_step("Step 2: Relay 5 ON (load MAF filter)", lambda: relays.on(5))
       # _run_step("Step 3: Hold after Relay 5 ON", wait_after=1.0)
       # _run_step("Step 4: Relay 5 OFF", lambda: relays.off(5))
       # _run_step("Step 5: Relay 6 ON (push MAF into position)", lambda: relays.on(6))
       # _run_step("Step 6: Hold after Relay 6 ON", wait_after=1.0)
       # _run_step("Step 7: Relay 6 OFF", lambda: relays.off(6))
        _run_step("Step 8: Move horizontal axis to FILTERING position", move_horizontal_to_filtering)
        _run_step("Step 9: Close plate (vertical axis)", move_vertical_close_plate)
        _run_step("Step 10: Valve 4 CLOSED (Relay 4 ON)", lambda: relays.on(4))
        _run_step("Step 24: Close PID valve", pid_controller.force_close, wait_after=2.0)
        _run_step("Step 11: Enable peristaltic pump", _enable_peristaltic)
        _run_step("Step 12: PID enable", lambda: pid_controller.set_enabled(True)) # enable after and point it to the flow rate
        _run_step("Step 13: Start reading flow sensor / volume", start_flow_meter)
        _run_step(f"Step 14: Run pump until total volume >= {target_volume_ml:.1f} mL", _volume_loop)
        _run_step("Step 15: Stop flow meter readings", stop_flow_meter, wait_after=0.5)
        _run_step(
            f"Step 15: Hold for {post_volume_wait_s:.1f}s after reaching target volume",
            wait_after=post_volume_wait_s,
        )
        _run_step("Step 16: Switch peristaltic to HIGH speed", lambda: motor_pump.set_speed_checked(False),wait_after=30.0)
        _run_step("Step 24: Close PID valve", pid_controller.force_close, wait_after=5.0)
        _run_step("Step 24: Home PID valve", _home_pid, wait_after=15.0)
        _run_step("Step 24: Close PID valve", pid_controller.force_close, wait_after=5.0)
        _run_step("Step 17: Stopping peristaltic pump", _disable_peristaltic)
        _run_step("Step 18: Valve 1 CLOSED (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 19: Syringe move to 0.1 mL", lambda: _syringe_move(0.1, 1.0))
        _run_step("Step 20: Valve 1 OPEN (Relay 1 ON)", lambda: relays.on(1))
        _run_step("Step 21: Syringe move to 1.6 mL", lambda: _syringe_move(1.5, 1.0)) # make value smaller if output sample is too much
        _run_step("Step 23: Valve 2 OPEN (Relay 2 ON)", lambda: relays.on(2))
        _run_step("Step 24: Valve 1 CLOSED (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 25: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 26: Syringe move to 0 mL", lambda: _syringe_move(0, 1.0))
        _run_step("Step 27: Valve 2 CLOSED (Relay 2 OFF)", lambda: relays.off(2))
        _run_step("Step 28: Syringe move to 2 mL", lambda: _syringe_move(2, 1.0))   # Here there is a wait for 1 min for incubation but syringe movement covers that so no extra wait
        _run_step("Step 29: Valve 4 OPEN (Relay 4 OFF)", lambda: relays.off(4))
        _run_step("Step 30: Valve 1 CLOSE (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 31: Valve 2 OPEN (Relay 2 ON)", lambda: relays.on(2))
        _run_step("Step 32: Syringe move to 0 mL", lambda: _syringe_move(0, 2.0), wait_after=5.0)
        _run_step("Step 24: Home PID valve", _home_pid, wait_after=15.0)
        _run_step("Step 33: Vertical axis to TOP (open plate)", move_vertical_open_plate)
        _run_step("Step 46: Relay 2 OFF", lambda: relays.off(2))
        _run_step("Step 47: Relay 3 OFF", lambda: relays.off(3))
       # _run_step("Step 1: Move horizontal axis to FILTER out position", move_horizontal_to_waste)
       # _run_step("Step 2: Relay 7 ON (empty MAF filter)", lambda: relays.on(7))
       # _run_step("Step 3: Hold after Relay 7 ON", wait_after=1.0)
       # _run_step("Step 4: Relay 7 OFF", lambda: relays.off(7))
       # _run_step("Step 5: Hold after Relay 7 OFF", wait_after=1.0)
        _run_step("Step 38: Horizontal axis to HOME (0 position)", move_horizontal_to_home)
    except SequenceAbort:
        _log("=== MAF sequence aborted ===")
        return

    _log("=== MAF sequence complete ===")
