import random
from shared.constants import (
    SHAPE_RADIUS, NORMAL, SHIELD, ICE, ILLUSION,
    HIGH_POINTS, LOW_POINTS, NEGATIVE_POINTS
)


def category_for_points(points: int) -> str:
    if points >= 3:
        return HIGH_POINTS

    if points >= 1:
        return LOW_POINTS

    return NEGATIVE_POINTS


def random_normal_points() -> int:
    points_category = random.choice([HIGH_POINTS, LOW_POINTS, NEGATIVE_POINTS])
    if points_category == HIGH_POINTS:
        return random.randint(3, 6)

    if points_category == LOW_POINTS:
        return random.randint(1, 2)

    return random.randint(-3, -1)


class Shape:
    def __init__(self, shape_id: int, x: int, y: int, spawn_time: int, lifetime: int):
        self.shape_id = shape_id
        self.x = x
        self.y = y
        self.radius = SHAPE_RADIUS
        self.spawn_time = spawn_time
        self.lifetime = lifetime
        self.expire_time = spawn_time + lifetime

    def is_expired(self, now: int) -> bool:
        return now >= self.expire_time

    def lifetime_ratio(self, now: int) -> float:
        remaining = self.expire_time - now
        return max(0.0, min(1.0, remaining / self.lifetime))

    def contains_point(self, x: int, y: int) -> bool:
        offset_x = x - self.x
        offset_y = y - self.y
        return offset_x * offset_x + offset_y * offset_y <= self.radius * self.radius

    def to_dict(self, now: int) -> dict:
        return {
            'id': self.shape_id,
            'kind': self.kind,
            'name': self.name,
            'x': self.x,
            'y': self.y,
            'radius': self.radius,
            'lifetime_ratio': round(self.lifetime_ratio(now), 3),
        }

    def on_click(self, player, opponents, now: int) -> None:
        raise NotImplementedError


class NormalShape(Shape):
    kind = NORMAL
    name = 'Normal'

    def __init__(self, points: int, **kwargs):
        super().__init__(**kwargs)
        self.points = points

    def points_category(self) -> str:
        return category_for_points(self.points)

    def to_dict(self, now: int) -> dict:
        data = super().to_dict(now)
        data['points'] = self.points
        return data

    def on_click(self, player, opponents, now: int) -> None:
        player.award_shape_points(self.points, now)
        player.register_shape_stress(self.points_category())


class ShieldShape(Shape):
    kind = SHIELD
    name = 'Shield'

    def on_click(self, player, opponents, now: int) -> None:
        player.apply_shield(now)


class IceShape(Shape):
    kind = ICE
    name = 'Ice'

    def on_click(self, player, opponents, now: int) -> None:
        for opponent in opponents:
            opponent.freeze(now)


class IllusionShape(NormalShape):
    kind = ILLUSION
    name = 'Illusion'

    def to_dict(self, now: int) -> dict:
        data = super().to_dict(now)
        data['kind'] = NormalShape.kind
        data['name'] = NormalShape.name
        return data

    def on_click(self, player, opponents, now: int) -> None:
        player.register_shape_stress(self.points_category())
