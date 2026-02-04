from typing import Callable, Optional

from domain.sleeper import InterruptibleSleeper


def run_maf_cleaning_sequence(
    *,
    stop_flag: Callable[[], bool],
    log: Optional[Callable[[str], None]] = None,
    relays=None,
    motor_pump=None,
    pid_controller=None,
    home_pid_valve: Optional[Callable[[], None]] = None,
    move_horizontal_to_filtering: Optional[Callable[[], None]] = None,
    move_horizontal_to_home: Optional[Callable[[], None]] = None,
    move_vertical_close_plate: Optional[Callable[[], None]] = None,
    move_vertical_open_plate: Optional[Callable[[], None]] = None,
    before_step: Optional[Callable[[str], None]] = None,
):
    """
    MAF CLEANING SEQUENCE (ported from Old_Codes/Cleaning_Sequence(1).py).
    """

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    sleeper = InterruptibleSleeper(stop_flag)

    class SequenceAbort(Exception):
        """Internal signal used to unwind the sequence safely."""

    def check_stop() -> bool:
        if not stop_flag():
            return False
        _log("[INFO] MAF cleaning sequence aborted by STOP.")
        try:
            if motor_pump is not None:
                motor_pump.set_enabled(False)
                motor_pump.set_direction(False)
                motor_pump.set_speed_checked(False)
        except Exception:
            pass
        try:
            if pid_controller is not None:
                pid_controller.set_enabled(False)
        except Exception:
            pass
        return True

    MIN_STEP_DELAY = 0.5
    POST_COMMAND_DELAY = 0.2

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
                raise SequenceAbort

        if success:
            _log(f"{step_label} completed")

        _wait_block(max(wait_after, MIN_STEP_DELAY))
        _wait_block(POST_COMMAND_DELAY)

    def _enable_peristaltic():
        if motor_pump is None:
            raise RuntimeError("motor_pump object is required")
        motor_pump.set_direction(True)
        motor_pump.set_speed_checked(True)
        motor_pump.set_enabled(True)

    def _disable_peristaltic():
        if motor_pump is None:
            return
        motor_pump.set_enabled(False)
        motor_pump.set_direction(False)
        motor_pump.set_speed_checked(False)

    def _home_pid():
        if home_pid_valve:
            home_pid_valve()
            return
        if pid_controller and hasattr(pid_controller, "homing_routine"):
            pid_controller.homing_routine()
            return
        raise RuntimeError("PID valve homing not available")

    def _close_pid():
        if pid_controller is None:
            raise RuntimeError("pid_controller is required for PID actions")
        pid_controller.force_close()

    def _pid_high_speed():
        if motor_pump is None:
            raise RuntimeError("motor_pump object is required")
        motor_pump.set_speed_checked(False)

    _log("=== MAF CLEANING sequence start ===")

    try:
        _run_step("Step 1: Initialization")
        _run_step("Step 2: Move horizontal axis to FILTERING position", move_horizontal_to_filtering)
        _run_step("Step 3: Close plate (vertical axis)", move_vertical_close_plate)
        _run_step("Step 4: Valve 4 CLOSED (Relay 4 ON)", lambda: relays.on(4))
        _run_step("Step 5: Enable peristaltic pump", _enable_peristaltic)
        _run_step("Step 6: Close PID valve (wait 25 sec)", _close_pid, wait_after=25.0)
        _run_step("Step 7: Valve 4 OPEN (Relay 4 OFF) (wait 3 sec)", lambda: relays.off(4), wait_after=3.0)
        _run_step("Step 8: Valve 4 CLOSED (Relay 4 ON)", lambda: relays.on(4))
        _run_step("Step 9: Home PID valve", _home_pid)
        _run_step("Step 10: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 10: Wait 20 min", wait_after=20 * 60.0)
        _run_step("Step 11: Valve 3 OPEN (Relay 3 OFF)", lambda: relays.off(3))
        _run_step("Step 13: Close PID valve", _close_pid)
        _run_step("Step 12: Prompt message to change inlet to WATER", action=None)
        _run_step("Step 14: Wait 10 sec", wait_after=10.0)
        _run_step("Step 15: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 14: Home PID valve", _home_pid, wait_after=10.0)
        _run_step("Step 17: Close PID valve", _close_pid)
        _run_step("Step 16: Valve 3 OPEN (Relay 3 OFF) (wait 10 sec)", lambda: relays.off(3), wait_after=10.0)
        _run_step("Step 15: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 14: Home PID valve", _home_pid, wait_after=10.0)
        _run_step("Step 17: Close PID valve", _close_pid)
        _run_step("Step 16: Valve 3 OPEN (Relay 3 OFF) (wait 10 sec)", lambda: relays.off(3), wait_after=10.0)
        _run_step("Step 22: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 23: Valve 4 OPEN (Relay 4 OFF) (wait 5 sec)", lambda: relays.off(4), wait_after=5.0)
        _run_step("Step 24: Valve 4 CLOSED (Relay 4 ON)", lambda: relays.on(4))
        _run_step("Step 25: Valve 3 OPEN (Relay 3 OFF)", lambda: relays.off(3))
        _run_step("Step 26: Prompt message to REMOVE inlet from water", action=None)
        _run_step("Step 27: Switch peristaltic to HIGH speed for 30 sec", _pid_high_speed, wait_after=30.0)
        _run_step("Step 28: Home PID valve", _home_pid, wait_after=2.0)
        _run_step("Step 29: Close PID valve", _close_pid, wait_after=10.0)
        _run_step("Step 30: Home PID valve", _home_pid, wait_after=15.0)
        _run_step("Step 31: Close PID valve", _close_pid, wait_after=10.0)
        _run_step("Step 32: Stop peristaltic pump", _disable_peristaltic)
        _run_step("Step 33: Home PID valve", _home_pid)
        _run_step("Step 34: Valve 4 OPEN (Relay 4 OFF)", lambda: relays.off(4))
        _run_step("Step 35: Open plate (vertical axis)", move_vertical_open_plate)
        _run_step("Step 36: Move horizontal axis to HOME position", move_horizontal_to_home)

    except SequenceAbort:
        _log("=== MAF CLEANING sequence aborted ===")
        return

    _log("=== MAF CLEANING sequence complete ===")
