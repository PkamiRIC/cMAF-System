from typing import Callable, Optional
import time

from domain.sleeper import InterruptibleSleeper


def run_sequence2(
    *,
    stop_flag: Callable[[], bool],
    log: Optional[Callable[[str], None]] = None,
    relays=None,  # expects .on(ch) / .off(ch)
    syringe=None,  # expects .goto_absolute(volume_ml, flow_ml_min)
    move_horizontal_to_filtering: Optional[Callable[[], None]] = None,
    move_horizontal_home: Optional[Callable[[], None]] = None,
    move_vertical_close_plate: Optional[Callable[[], None]] = None,
    move_vertical_open_plate: Optional[Callable[[], None]] = None,
    select_rotary_port: Optional[Callable[[int], None]] = None,
    reset_flow_totals: Optional[Callable[[], None]] = None,
    start_flow_meter: Optional[Callable[[], None]] = None,
    stop_flow_meter: Optional[Callable[[], None]] = None,
    get_total_volume_ml: Optional[Callable[[], float]] = None,
    before_step: Optional[Callable[[str], None]] = None,
    syringe_flow_ml_min: float = 2.0,
    target_volume_ml: float = 50.0,
    early_complete_ratio: float = 0.925,
    early_complete_wait_s: float = 10.0,
    stagnant_timeout_s: float = 20.0,
    stagnant_epsilon_ml: float = 0.001,
):
    """Sequence 2."""

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    sleeper = InterruptibleSleeper(stop_flag)

    class SequenceAbort(Exception):
        pass

    MIN_STEP_DELAY = 0.5

    def _wait_block(duration: float):
        duration = max(duration, 0.0)
        if duration == 0:
            return
        try:
            sleeper.sleep(duration)
        except InterruptedError:
            raise SequenceAbort

    def _run_step(
        step_label: str,
        action: Optional[Callable[[], None]] = None,
        wait_after: float = MIN_STEP_DELAY,
    ):
        if before_step:
            try:
                before_step(step_label)
            except Exception:
                raise SequenceAbort

        if stop_flag():
            _log("[INFO] Sequence 2 aborted by STOP.")
            raise SequenceAbort

        _log(step_label)
        ok = True

        if action:
            try:
                action()
            except Exception as exc:
                ok = False
                _log(f"[WARN] {step_label} failed: {exc}")
                raise SequenceAbort

        if ok:
            _log(f"{step_label} completed")

        _wait_block(wait_after)

    def _syringe_move(target_ml: float):
        if syringe is None:
            raise RuntimeError("Syringe unavailable")
        syringe.goto_absolute(target_ml, float(syringe_flow_ml_min))

    def _set_port(port: int):
        if select_rotary_port is None:
            raise RuntimeError("Rotary valve adapter unavailable")
        select_rotary_port(port)

    def _stop_flow_meter_safe():
        if stop_flow_meter is None:
            return
        for attempt in range(1, 4):
            try:
                stop_flow_meter()
                return
            except Exception as exc:
                _log(f"[WARN] Stop flow meter failed (attempt {attempt}/3): {exc}")
                _wait_block(0.2)
        _log("[WARN] Stop flow meter failed after retries; continuing sequence")

    def _volume_loop():
        if get_total_volume_ml is None:
            raise RuntimeError("Flow meter total volume adapter unavailable")

        early_threshold_ml = float(target_volume_ml) * early_complete_ratio
        last_total: Optional[float] = None
        stagnant_since: Optional[float] = None

        while True:
            if stop_flag():
                _log("[INFO] Sequence 2 aborted by STOP.")
                raise SequenceAbort
            try:
                total = float(get_total_volume_ml())
            except Exception:
                total = 0.0
            _log(f"  [Flow] Total volume = {total:.2f} mL")

            if total >= early_threshold_ml:
                _log(
                    f"  [Flow] Reached {early_complete_ratio * 100:.1f}% of target "
                    f"({total:.2f}/{target_volume_ml:.2f} mL). Holding {early_complete_wait_s:.1f}s."
                )
                _wait_block(early_complete_wait_s)
                break

            now = time.monotonic()
            if last_total is None or abs(total - last_total) > stagnant_epsilon_ml:
                last_total = total
                stagnant_since = now
            else:
                if stagnant_since is None:
                    stagnant_since = now
                if (now - stagnant_since) >= stagnant_timeout_s:
                    _log(
                        f"  [Flow] Total volume unchanged for {stagnant_timeout_s:.1f}s "
                        f"at {total:.2f} mL. Proceeding to next step."
                    )
                    break

            if total >= target_volume_ml:
                break
            _wait_block(0.2)

    def _run_flow_until_target_or_contingency():
        # If flow-meter adapters are not wired, preserve legacy behavior.
        if (
            reset_flow_totals is None
            or start_flow_meter is None
            or stop_flow_meter is None
            or get_total_volume_ml is None
        ):
            _log("[WARN] Flow meter adapters unavailable in Sequence 2; using fallback wait 1s.")
            _wait_block(1.0)
            return

        reset_flow_totals()
        start_flow_meter()
        try:
            _volume_loop()
        finally:
            _stop_flow_meter_safe()

    _log("=== Sequence 2 start ===")

    try:
        # INITIAL AXIS POSITIONING
        _run_step("Step 1: Move X-Axis to FILTERING", move_horizontal_to_filtering)
        _run_step("Step 2: Close filter (vertical axis)", move_vertical_close_plate)

        # MAIN OPERATIONS

        _run_step("Step 3: Rotary Valve -> Port 3", lambda: _set_port(3))
        _run_step("Step 4: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))

        _run_step("Step 5: Rotary Valve -> Port 1", lambda: _set_port(1))
        _run_step("Step 6: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        _run_step("Step 7: Rotary Valve -> Port 3", lambda: _set_port(3))
        _run_step("Step 8: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))

        _run_step("Step 9: Rotary Valve -> Port 5", lambda: _set_port(5))
        _run_step("Step 10: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        _run_step("Step 11: Rotary Valve -> Port 4", lambda: _set_port(4))
        _run_step("Step 12: Syringe -> 2.0 mL", lambda: _syringe_move(2.0))

        _run_step("Step 13: Rotary Valve -> Port 5", lambda: _set_port(5))
        _run_step("Step 14: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        # Valve 1 ON
        _run_step("Step 15: Valve 1 ON", lambda: relays.on(1))

        _run_step("Step 16: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))

        # Optional wait (just a delay)
        _run_step("Step 17: Optional wait", None, wait_after=1.0)

        _run_step("Step 18: Valve 1 OFF", lambda: relays.off(1))
        _run_step("Step 19: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        _run_step("Step 20: Rotary Valve -> Port 6", lambda: _set_port(6))
        _run_step("Step 21: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))

        _run_step("Step 22: Rotary Valve -> Port 1", lambda: _set_port(1))

        _run_step(
            "Step 23: Run flow until target reached (or >=92.5% + hold, or stagnant 20s)",
            _run_flow_until_target_or_contingency,
        )

        _run_step("Step 24: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        # Repeat cycle
        for i in range(2):
            _run_step(f"Step 25.{i}: Rotary Valve -> Port 3", lambda: _set_port(3))
            _run_step(f"Step 26.{i}: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))
            _run_step(f"Step 27.{i}: Rotary Valve -> Port 5", lambda: _set_port(5))
            _run_step(f"Step 28.{i}: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        # Final yellow block
        _run_step("Step 29: Rotary Valve -> Port 3", lambda: _set_port(3))
        _run_step("Step 30: Syringe -> 1.0 mL", lambda: _syringe_move(1.0))

        _run_step("Step 31: Rotary Valve -> Port 5", lambda: _set_port(5))

        _run_step("Step 32: Valve 2 ON", lambda: relays.on(2))
        _run_step("Step 33: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))
        _run_step("Step 34: Valve 2 OFF", lambda: relays.off(2))

        # Post-rinse block
        _run_step("Step 35: Rotary Valve -> Port 4", lambda: _set_port(4))
        _run_step("Step 36: Syringe -> 2.5 mL", lambda: _syringe_move(2.5))

        _run_step("Step 37: Rotary Valve -> Port 5", lambda: _set_port(5))
        _run_step("Step 38: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))

        _run_step("Step 39: Rotary Valve -> Port 4", lambda: _set_port(4))
        _run_step("Step 40: Syringe -> 1.0 mL", lambda: _syringe_move(1.0))

        _run_step("Step 41: Rotary Valve -> Port 5", lambda: _set_port(5))

        _run_step("Step 42: Valve 2 ON", lambda: relays.on(2))
        _run_step("Step 43: Syringe -> 0.0 mL", lambda: _syringe_move(0.0))
        _run_step("Step 44: Valve 2 OFF", lambda: relays.off(2))

        # FINAL POSITIONING
        _run_step("Step 45: Open filter", move_vertical_open_plate)
        _run_step("Step 46: Move X-Axis HOME", move_horizontal_home)

    except SequenceAbort:
        _log("=== Sequence 2 aborted ===")
        return

    _log("=== Sequence 2 complete ===")
