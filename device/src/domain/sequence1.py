from typing import Callable, Optional
import time

from domain.sleeper import InterruptibleSleeper


def run_maf_sampling_sequence(
    *,
    stop_flag: Callable[[], bool],
    reset_flow_totals: Callable[[], None],
    start_flow_meter: Callable[[], None],
    stop_flow_meter: Callable[[], None],
    get_total_volume_ml: Callable[[], float],
    log: Optional[Callable[[str], None]] = None,
    relays=None,
    motor_pump=None,
    pid_controller=None,
    home_pid_valve: Optional[Callable[[], None]] = None,
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
    early_complete_ratio: float = 0.925,
    early_complete_wait_s: float = 10.0,
    stagnant_timeout_s: float = 20.0,
    stagnant_epsilon_ml: float = 0.001,
    before_step: Optional[Callable[[str], None]] = None,
):
    """
    MAF sequence (ported from Old_Codes/MAF_Sequence_v1.py).
    """

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    sleeper = InterruptibleSleeper(stop_flag)

    def check_stop() -> bool:
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
    POST_COMMAND_DELAY = 0.2

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
                raise SequenceAbort
        if success:
            _log(f"{step_label} completed")
        _wait_block(max(wait_after, MIN_STEP_DELAY))
        _wait_block(POST_COMMAND_DELAY)

    def _volume_loop():
        early_threshold_ml = float(target_volume_ml) * early_complete_ratio
        last_total: Optional[float] = None
        stagnant_since: Optional[float] = None

        while True:
            if stop_flag():
                check_stop()
                raise SequenceAbort
            try:
                total = float(get_total_volume_ml())
            except Exception:
                total = 0.0
            _log(f"  [Flow] Total volume = {total:.2f} mL")

            # Contingency 1: if we reach 92.5% of target, hold 10s and continue.
            if total >= early_threshold_ml:
                _log(
                    f"  [Flow] Reached {early_complete_ratio * 100:.1f}% of target "
                    f"({total:.2f}/{target_volume_ml:.2f} mL). Holding {early_complete_wait_s:.0f}s."
                )
                _wait_block(early_complete_wait_s)
                break

            # Contingency 2: if total volume is stagnant for >20s, continue.
            now = time.monotonic()
            if last_total is None or abs(total - last_total) > stagnant_epsilon_ml:
                last_total = total
                stagnant_since = now
            else:
                if stagnant_since is None:
                    stagnant_since = now
                stagnant_for = now - stagnant_since
                if stagnant_for >= stagnant_timeout_s:
                    _log(
                        f"  [Flow] Total volume unchanged for {stagnant_timeout_s:.0f}s "
                        f"at {total:.2f} mL. Proceeding to next step."
                    )
                    break

            if total >= target_volume_ml:
                break
            _wait_block(0.2)

    def _enable_peristaltic():
        motor_pump.set_direction(False)
        motor_pump.set_speed_checked(True)
        motor_pump.set_enabled(True)

    def _disable_peristaltic():
        motor_pump.set_enabled(False)
        motor_pump.set_direction(False)
        motor_pump.set_speed_checked(False)

    def _stop_flow_meter_safe():
        for attempt in range(1, 4):
            try:
                stop_flow_meter()
                return
            except Exception as exc:
                _log(f"[WARN] Stop flow meter failed (attempt {attempt}/3): {exc}")
                _wait_block(0.2)
        _log("[WARN] Stop flow meter failed after retries; continuing sequence")

    def _syringe_move(target_ml: float, flow_ml_min: float):
        if syringe is None:
            raise RuntimeError("Syringe adapter unavailable")
        syringe.goto_absolute(target_ml, flow_ml_min)

    def _home_pid():
        if home_pid_valve:
            home_pid_valve()
            return
        if pid_controller and hasattr(pid_controller, "homing_routine"):
            pid_controller.homing_routine()
            return
        raise RuntimeError("PID valve homing not available")

    _log("=== MAF sequence start ===")

    try:
        _run_step("Step 1: Initialization", reset_flow_totals)
        _run_step("Step 2: Relay 5 ON (load MAF filter)", lambda: relays.on(5))
        _run_step("Step 3: Hold after Relay 5 ON", wait_after=4.0)
        _run_step("Step 4: Relay 5 OFF", lambda: relays.off(5), wait_after=4.0)
        _run_step("Step 5: Relay 6 ON (push MAF into position)", lambda: relays.on(6), wait_after=4.0)
        _run_step("Step 6: Hold after Relay 6 ON", wait_after=1.0)
        _run_step("Step 7: Relay 6 OFF", lambda: relays.off(6), wait_after=4.0)
        _run_step("Step 8: Move horizontal axis to FILTERING position", move_horizontal_to_filtering)
        _run_step("Step 9: Close plate (vertical axis)", move_vertical_close_plate)
        _run_step("Step 10: Valve 4 CLOSED (Relay 4 ON)", lambda: relays.on(4))
        _run_step("Step 11: Close PID valve", pid_controller.force_close, wait_after=0.0)
        _run_step("Step 12: Enable peristaltic pump", _enable_peristaltic)
        _run_step("Step 13: PID enable", lambda: pid_controller.set_enabled(True))
        _run_step("Step 14: Start reading flow sensor / volume", start_flow_meter)
        _run_step(
            (
                f"Step 15: Run pump until target reached "
                f"(or >=92.5% +10s hold, or no flow change for 20s)"
            ),
            _volume_loop,
        )
        _run_step("Step 16: Stop flow meter readings", _stop_flow_meter_safe, wait_after=0.5)
        _run_step(
            f"Step 17: Hold for {post_volume_wait_s:.1f}s after reaching target volume",
            wait_after=post_volume_wait_s,
        )
        _run_step(
            "Step 18: Switch peristaltic to HIGH speed",
            lambda: motor_pump.set_speed_checked(False),
            wait_after=30.0,
        )
        _run_step("Step 19: Disable PID valve control", lambda: pid_controller.set_enabled(False))
        _run_step("Step 20: Close PID valve", pid_controller.force_close, wait_after=10.0)
        _run_step("Step 21: Home PID valve", _home_pid, wait_after=15.0)
        _run_step("Step 22: Close PID valve", pid_controller.force_close, wait_after=10.0)
        _run_step("Step 23: Stopping peristaltic pump", _disable_peristaltic)
        _run_step("Step 24: Enable temperature controller", enable_temp_controller)
        _run_step("Step 25: Valve 1 CLOSED (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 26: Syringe move to 0.1 mL", lambda: _syringe_move(0.1, 1.0))
        _run_step("Step 27: Valve 1 OPEN (Relay 1 ON)", lambda: relays.on(1))
        _run_step("Step 28: Syringe move to 1.6 mL", lambda: _syringe_move(1.5, 1.0))
        _run_step("Step 29: Valve 2 OPEN (Relay 2 ON)", lambda: relays.on(2))
        _run_step("Step 30: Valve 1 CLOSED (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 31: Valve 3 CLOSED (Relay 3 ON)", lambda: relays.on(3))
        _run_step("Step 32: Syringe move to 0 mL", lambda: _syringe_move(0, 1.0))
        _run_step("Step 33: Valve 2 CLOSED (Relay 2 OFF)", lambda: relays.off(2))
        _run_step("Step 34: Syringe move to 2 mL", lambda: _syringe_move(2, 1.0))
        _run_step("Step 35: Wait to reach temperature (READY)", wait_for_temp_ready)
        _run_step("Step 36: Wait for MAF heating", wait_for_maf_heating)
        _run_step("Step 37: Disable temperature controller", disable_temp_controller)
        _run_step("Step 38: Enable fan", lambda: relays.on(8))
        _run_step("Step 39: Valve 4 OPEN (Relay 4 OFF)", lambda: relays.off(4))
        _run_step("Step 40: Valve 1 CLOSE (Relay 1 OFF)", lambda: relays.off(1))
        _run_step("Step 41: Valve 2 OPEN (Relay 2 ON)", lambda: relays.on(2))
        _run_step(
            "Step 42: Syringe move to 0 mL", lambda: _syringe_move(0, 2.0), wait_after=5.0
        )
        _run_step("Step 43: Vertical axis to TOP (open plate)", move_vertical_open_plate)
        _run_step("Step 44: Horizontal axis to HOME (0 position)", move_horizontal_to_waste)
        _run_step("Step 45: Eject MAF (Relay 7 ON)", lambda: relays.on(7))
        _run_step("Step 46: Hold after ejecting MAF", wait_after=4.0)
        _run_step("Step 47: Relay 7 OFF", lambda: relays.off(7), wait_after=4.0)
        _run_step("Step 48: Disable Fan (Relay 8 OFF)", lambda: relays.off(8))
        _run_step("Step 49: Home PID valve", _home_pid, wait_after=15.0)
        _run_step("Step 50: Relay 2 OFF", lambda: relays.off(2))
        _run_step("Step 51: Relay 3 OFF", lambda: relays.off(3))
        _run_step("Step 52: Horizontal axis to HOME (0 position)", move_horizontal_to_home)
    except SequenceAbort:
        _log("=== MAF sequence aborted ===")
        return

    _log("=== MAF sequence complete ===")
