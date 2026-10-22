import math
import random
from shared.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    STRESS_SLOW_MIN, STRESS_JUMP_MIN, STRESS_TRAIL_MIN,
    CURSOR_SLOW_FRACTION_LOW, CURSOR_SLOW_FRACTION_HIGH,
    CURSOR_JUMP_INTERVAL_MS, CURSOR_JUMP_MIN_PX, CURSOR_JUMP_MAX_PX,
    TRAIL_LENGTH, CALIBRATION_MS, SENSITIVITY_WINDOW_MS,
    SENSITIVITY_SPIKE_FACTOR, SENSITIVITY_SPIKE_HOLD_MS
)


def speed_reduction_for_stress(stress: float) -> float:
    # Percentage reductions never add up: a player in a high band gets that
    # band's single value, not the sum of every band below it.
    if stress >= STRESS_TRAIL_MIN:
        return CURSOR_SLOW_FRACTION_HIGH

    if stress >= STRESS_SLOW_MIN:
        return CURSOR_SLOW_FRACTION_LOW

    return 0.0


class StressCursor:
    def __init__(self, x: float, y: float, now: int):
        self.reset(x, y, now)

    def reset(self, x: float, y: float, now: int) -> None:
        self._x = float(x)
        self._y = float(y)
        self._started_at = now

        self._baseline_speed = 0.0
        self._calibration_total = 0.0
        self._calibration_count = 0
        self._recent_speeds: list[tuple[int, float]] = []
        self._sensitivity_correction = 1.0
        self._spike_started_at = 0

        self._jump_window_end = now
        self._jump_at: int | None = None

        self.trail_positions: list[tuple[float, float]] = []

    @property
    def position(self) -> tuple[float, float]:
        return self._x, self._y

    @property
    def sensitivity_correction(self) -> float:
        return self._sensitivity_correction

    def update(self, delta_x: float, delta_y: float, stress: float, now: int) -> None:
        speed = math.hypot(delta_x, delta_y)
        calibrating = now - self._started_at < CALIBRATION_MS
        self._record_speed(speed, now, calibrating)

        if calibrating:
            reduction = 0.0
        else:
            self._update_sensitivity_correction(now)
            reduction = speed_reduction_for_stress(stress)

        scale = (1.0 - reduction) * self._sensitivity_correction
        self._move_to(self._x + delta_x * scale, self._y + delta_y * scale)

        self._update_jump(stress, now)
        self._update_trail(stress)

    def _move_to(self, x: float, y: float) -> None:
        self._x = max(0.0, min(float(SCREEN_WIDTH), x))
        self._y = max(0.0, min(float(SCREEN_HEIGHT), y))

    def _record_speed(self, speed: float, now: int, calibrating: bool) -> None:
        if speed > 0.0:
            self._recent_speeds.append((now, speed))
            if calibrating:
                self._calibration_total += speed
                self._calibration_count += 1

        oldest = now - SENSITIVITY_WINDOW_MS
        while self._recent_speeds and self._recent_speeds[0][0] < oldest:
            self._recent_speeds.pop(0)

        if calibrating and self._calibration_count > 0:
            self._baseline_speed = self._calibration_total / self._calibration_count

    def _rolling_speed(self) -> float:
        if not self._recent_speeds:
            return 0.0

        return sum(speed for _, speed in self._recent_speeds) / len(self._recent_speeds)

    def _update_sensitivity_correction(self, now: int) -> None:
        # The baseline is the player's own movement scale from the calibration
        # window. Comparing against it, rather than against the live speed,
        # is what catches someone raising their OS sensitivity mid-round to
        # out-run the stress slowdown.
        rolling = self._rolling_speed()
        if rolling <= 0.0:
            return

        if self._baseline_speed <= 0.0:
            self._baseline_speed = rolling

        if rolling <= self._baseline_speed * SENSITIVITY_SPIKE_FACTOR:
            self._spike_started_at = 0
            self._sensitivity_correction = 1.0
            return

        if self._spike_started_at == 0:
            self._spike_started_at = now
        elif now - self._spike_started_at >= SENSITIVITY_SPIKE_HOLD_MS:
            self._sensitivity_correction = self._baseline_speed / rolling

    def _update_jump(self, stress: float, now: int) -> None:
        if stress < STRESS_JUMP_MIN:
            self._jump_window_end = now
            self._jump_at = None
            return

        if now >= self._jump_window_end:
            self._jump_window_end = now + CURSOR_JUMP_INTERVAL_MS
            self._jump_at = now + random.randint(0, CURSOR_JUMP_INTERVAL_MS)

        if self._jump_at is None or now < self._jump_at:
            return

        self._jump_at = None
        distance = random.randint(CURSOR_JUMP_MIN_PX, CURSOR_JUMP_MAX_PX)
        angle = random.uniform(0.0, 2.0 * math.pi)
        self._move_to(
            self._x + distance * math.cos(angle),
            self._y + distance * math.sin(angle),
        )

    def _update_trail(self, stress: float) -> None:
        if stress < STRESS_TRAIL_MIN:
            self.trail_positions.clear()
            return

        self.trail_positions.append((self._x, self._y))
        if len(self.trail_positions) > TRAIL_LENGTH:
            self.trail_positions.pop(0)
