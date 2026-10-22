from shared.constants import (
    START_STAMINA, START_STRESS,
    STAMINA_CLICK_COST, STAMINA_IDLE_RECOVERY, STAMINA_RECOVERY_INTERVAL_MS,
    STAMINA_HIGH_MIN, STAMINA_DIM_MIN, STAMINA_HIDDEN_MIN,
    STRESS_EMPTY_CLICK, STRESS_LOW_SHAPE, STRESS_NEGATIVE_SHAPE, STRESS_HIGH_SHAPE,
    STRESS_DECAY_PER_INTERVAL, STRESS_DECAY_INTERVAL_MS,
    STRESS_TRAIL_MIN, STRESS_DOUBLE_ILLUSION_MIN, ILLUSION_INTERVAL_MS,
    HIGH_POINTS, LOW_POINTS, NEGATIVE_POINTS,
    SHIELD_TIME, ICE_TIME
)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class Stamina:
    def __init__(self, value: float = START_STAMINA, now: int = 0):
        self._value = _clamp(float(value))
        self._last_recovery_at = now

    @property
    def value(self) -> float:
        return self._value

    def spend_for_click(self, now: int) -> None:
        self._value = _clamp(self._value - STAMINA_CLICK_COST)
        self._last_recovery_at = now

    def recover_while_idle(self, now: int) -> None:
        while now - self._last_recovery_at >= STAMINA_RECOVERY_INTERVAL_MS:
            self._last_recovery_at += STAMINA_RECOVERY_INTERVAL_MS
            self._value = _clamp(self._value + STAMINA_IDLE_RECOVERY)

    def restart_recovery_timer(self, now: int) -> None:
        self._last_recovery_at = now

    def is_high(self) -> bool:
        return self._value >= STAMINA_HIGH_MIN

    def hides_shapes(self) -> bool:
        return STAMINA_HIDDEN_MIN <= self._value < STAMINA_DIM_MIN

    def is_exhausted(self) -> bool:
        return self._value < STAMINA_HIDDEN_MIN

    def score_multiplier(self) -> int:
        return 2 if self.is_high() else 1


class Stress:
    def __init__(self, value: float = START_STRESS, now: int = 0):
        self._value = _clamp(float(value))
        self._last_decay_at = now

    @property
    def value(self) -> float:
        return self._value

    def register_shape_click(self, category: str) -> None:
        if category == NEGATIVE_POINTS:
            self._value = _clamp(self._value + STRESS_NEGATIVE_SHAPE)
        elif category == LOW_POINTS:
            self._value = _clamp(self._value + STRESS_LOW_SHAPE)
        elif category == HIGH_POINTS:
            self._value = _clamp(self._value + STRESS_HIGH_SHAPE)

    def register_empty_click(self) -> None:
        self._value = _clamp(self._value + STRESS_EMPTY_CLICK)

    def decay_while_stamina_high(self, now: int) -> None:
        while now - self._last_decay_at >= STRESS_DECAY_INTERVAL_MS:
            self._last_decay_at += STRESS_DECAY_INTERVAL_MS
            self._value = _clamp(self._value - STRESS_DECAY_PER_INTERVAL)

    def restart_decay_timer(self, now: int) -> None:
        self._last_decay_at = now

    def sees_illusions(self) -> bool:
        return self._value >= STRESS_TRAIL_MIN

    def illusion_interval_ms(self) -> int:
        if self._value >= STRESS_DOUBLE_ILLUSION_MIN:
            return ILLUSION_INTERVAL_MS // 2

        return ILLUSION_INTERVAL_MS


class PlayerState:
    def __init__(self, name: str, slot: int, player_id: str, now: int = 0):
        self.name = name
        self.slot = slot
        self.player_id = player_id

        self.score = 0
        self.stamina = Stamina(now=now)
        self.stress = Stress(now=now)

        self.shield_until = 0
        self.frozen_until = 0

        self.connected = True

    def is_shielded(self, now: int) -> bool:
        return now < self.shield_until

    def is_frozen(self, now: int) -> bool:
        return now < self.frozen_until

    def can_click(self, now: int) -> bool:
        return not self.is_frozen(now) and not self.stamina.is_exhausted()

    def register_click(self, now: int) -> bool:
        if not self.can_click(now):
            return False

        self.stamina.spend_for_click(now)
        return True

    def register_empty_click(self) -> None:
        self.stress.register_empty_click()

    def register_shape_stress(self, category: str) -> None:
        self.stress.register_shape_click(category)

    def apply_shield(self, now: int) -> None:
        self.shield_until = max(now, self.shield_until) + SHIELD_TIME

    def freeze(self, now: int) -> None:
        self.frozen_until = max(now, self.frozen_until) + ICE_TIME

    def award_shape_points(self, points: int, now: int) -> int:
        amount = points
        if amount > 0:
            amount *= self.stamina.score_multiplier()
        elif self.is_shielded(now):
            amount = 0
        elif self.stamina.is_high():
            # int() truncates toward zero, so a halved penalty is never harsher
            # than the original. Floor division would turn -3 into -2.
            amount = int(amount / 2)

        self.score += amount
        return amount

    def apply_passive_changes(self, now: int) -> None:
        if self.is_frozen(now):
            self.stamina.restart_recovery_timer(now)
            self.stress.restart_decay_timer(now)
            return

        self.stamina.recover_while_idle(now)
        if self.stamina.is_high():
            self.stress.decay_while_stamina_high(now)
        else:
            self.stress.restart_decay_timer(now)

    def to_dict(self, now: int) -> dict:
        return {
            'name': self.name,
            'slot': self.slot,
            'score': self.score,
            'stamina': round(self.stamina.value, 1),
            'stress': round(self.stress.value, 1),
            'shielded': self.is_shielded(now),
            'frozen': self.is_frozen(now),
            'exhausted': self.stamina.is_exhausted(),
            'connected': self.connected,
        }
