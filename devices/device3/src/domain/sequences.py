from typing import Callable, Optional

from domain.sleeper import InterruptibleSleeper


def run_maf_sampling_sequence(
    *,
    stop_flag: Callable[[], bool],
    log: Optional[Callable[[str], None]] = None,
    relays=None,  # expects .on(ch) / .off(ch)
    syringe=None,  # expects .goto_absolute(volume_ml, flow_ml_min)
    move_horizontal_to_filtering: Optional[Callable[[], None]] = None,
    move_vertical_close_plate: Optional[Callable[[], None]] = None,
    select_rotary_port: Optional[Callable[[int], None]] = None,
    before_step: Optional[Callable[[str], None]] = None,
    init: Optional[Callable[[], None]] = None,
    wait_after: Optional[Callable[[float], None]] = None,
    wait_after_relay5_s: float = 1.0,
    wait_after_relay6_s: float = 1.0,
    syringe_flow_ml_min: float = 1.0,
):
    """
    MAF sampling / injection sequence (28 steps).
    """

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    sleeper = InterruptibleSleeper(stop_flag)

    class SequenceAbort(Exception):
        """Internal signal used to unwind the sequence safely."""

    MIN_STEP_DELAY = 0.5

    def _wait_block(duration: float):
        duration = max(duration, 0.0)
        if duration == 0.0:
            return
        try:
            sleeper.sleep(duration)
        except InterruptedError:
            if stop_flag():
                raise SequenceAbort
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
                if stop_flag():
                    raise SequenceAbort
                raise SequenceAbort
            except Exception as exc:
                _log(f"[WARN] Step prompt failed ({step_label}): {exc}")

        if stop_flag():
            _log("[INFO] MAF sampling sequence aborted by STOP.")
            raise SequenceAbort

        _log(step_label)
        success = True
        if action:
            try:
                action()
            except SequenceAbort:
                raise
            except InterruptedError:
                if stop_flag():
                    raise SequenceAbort
                raise SequenceAbort
            except Exception as exc:
                success = False
                _log(f"[WARN] {step_label} failed: {exc}")
        if success:
            _log(f"{step_label} completed")

        _wait_block(max(wait_after, MIN_STEP_DELAY))

    def _syringe_move(target_ml: float, flow_override: Optional[float] = None):
        if syringe is None:
            raise RuntimeError("Syringe adapter unavailable")
        flow = syringe_flow_ml_min if flow_override is None else float(flow_override)
        syringe.goto_absolute(target_ml, flow)

    def _set_port(port: int):
        if select_rotary_port is None:
            raise RuntimeError("Rotary valve adapter unavailable")
        select_rotary_port(port)

    _log("=== MAF sampling sequence start ===")

    try:
        # 1. Initialization
        _run_step("Step 1: Initialization", init)

        # 2-7: load and push MAF filter with relays 5 and 6
        _run_step("Step 2: Relay 5 ON (load MAF filter)", lambda: relays.on(5))
        _run_step(
            "Step 3: Wait after Relay 5 ON",
            wait_after=max(wait_after_relay5_s, MIN_STEP_DELAY),
        )
        _run_step("Step 4: Relay 5 OFF", lambda: relays.off(5))
        _run_step("Step 5: Relay 6 ON (push MAF in position)", lambda: relays.on(6))
        _run_step(
            "Step 6: Wait after Relay 6 ON",
            wait_after=max(wait_after_relay6_s, MIN_STEP_DELAY),
        )
        _run_step("Step 7: Relay 6 OFF", lambda: relays.off(6))

        # 8-9: move axes
        _run_step(
            "Step 8: Horizontal axis to FILTERING position (below plate)",
            move_horizontal_to_filtering,
        )
        _run_step(
            "Step 9: Close plate (vertical axis)",
            move_vertical_close_plate,
        )

        # 10-11: air 0.1 mL
        _run_step("Step 10: Rotary Valve Port 4 (AIR)", lambda: _set_port(4))
        _run_step("Step 11: Syringe suck AIR to 0.1 mL", lambda: _syringe_move(0.1, 1.0))

        # 12-13: sample 1.5 mL  (total 1.6 mL)
        _run_step("Step 12: Rotary Valve Port 2 (SAMPLE)", lambda: _set_port(2))
        _run_step(
            "Step 13: Syringe suck SAMPLE to 1.5 mL (0.1 air + 1.5 sample)",
            lambda: _syringe_move(1.6, 1.0),
        )

        # 14-15: inject into MAF
        _run_step("Step 14: Rotary Valve Port 5 (MAF)", lambda: _set_port(5))
        _run_step("Step 15: Syringe inject SAMPLE (to 0.0 mL)", lambda: _syringe_move(0.0, 0.2))

        # 16-19: push additional 2.0 mL air through MAF
        _run_step("Step 16: Rotary Valve Port 4 (AIR)", lambda: _set_port(4))
        _run_step("Step 17: Syringe suck AIR to 2.0 mL", lambda: _syringe_move(2.0, 2.0))
        _run_step("Step 18: Rotary Valve Port 5 (MAF)", lambda: _set_port(5))
        _run_step("Step 19: Syringe inject AIR (to 0.0 mL)", lambda: _syringe_move(0.0, 1.0))

        # 20-23: air + H2O plug (0.1 air + 1.2 H2O)
        _run_step("Step 20: Rotary Valve Port 4 (AIR)", lambda: _set_port(4))
        _run_step("Step 21: Syringe suck AIR to 0.1 mL", lambda: _syringe_move(0.1, 1.0))
        _run_step("Step 22: Rotary Valve Port 3 (H2O)", lambda: _set_port(3))
        _run_step(
            "Step 23: Syringe suck H2O to 1.3 mL (0.1 air + 1.2 H2O)",
            lambda: _syringe_move(1.3, 1.0),
        )

        # 24-26: inject plug through MAF with Valve 2 open
        _run_step("Step 24: Rotary Valve Port 5 (MAF)", lambda: _set_port(5))
        _run_step("Step 25: Relay 2 ON (Valve 2 OPEN)", lambda: relays.on(2))
        _run_step("Step 26: Syringe inject to 0.0 mL", lambda: _syringe_move(0.0, 1.0))

        # Repeat 16-19 to push more air
        _run_step("Step 16: Rotary Valve Port 4 (AIR)", lambda: _set_port(4))
        _run_step("Step 17: Syringe suck AIR to 2.0 mL", lambda: _syringe_move(2.0, 2.0))
        _run_step("Step 18: Rotary Valve Port 5 (MAF)", lambda: _set_port(5))
        _run_step("Step 19: Syringe inject AIR (to 0.0 mL)", lambda: _syringe_move(0.0, 1.0))

        # Step 27: Re-run initialization (homes all axes)
        _run_step("Step 27: Re-initialization / Homing", init)

        # Step 28: Turn all relays OFF
        _run_step("Step 28: Turn ALL relays OFF", lambda: [relays.off(ch) for ch in range(1, 9)])

    except SequenceAbort:
        _log("=== MAF sampling sequence aborted ===")
        return

    _log("=== MAF sampling sequence complete ===")


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
    before_step: Optional[Callable[[str], None]] = None,
    syringe_flow_ml_min: float = 2.0,
):
    """Sequence 2 (user-specified)."""

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

        _run_step("Step 23: Optional wait", None, wait_after=1.0)

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
