import random
import threading
from shared.constants import (
    PLAY_LEFT, PLAY_TOP, PLAY_WIDTH, PLAY_HEIGHT,
    MAX_SHAPES_ON_SCREEN, SHAPE_SPAWN_MIN, SHAPE_SPAWN_MAX,
    SHAPE_LIFETIME_MIN, SHAPE_LIFETIME_MAX, SHAPE_RADIUS,
    NORMAL_SHAPE_CHANCE, SHIELD_SHAPE_CHANCE, HIDDEN_SHAPE_CHANCE,
    COUNTDOWN_SECONDS,
    WAITING_PHASE, COUNTDOWN_PHASE, PLAYING_PHASE, FINISHED_PHASE
)
from game.models import PlayerState
from game.shapes import (
    NormalShape, ShieldShape, IceShape, IllusionShape, random_normal_points
)


class GameSession:
    def __init__(self, session_id: str, host_name: str, capacity: int, duration_seconds: int):
        self.session_id = session_id
        self.host_name = host_name
        self.capacity = capacity
        self.duration_seconds = duration_seconds

        self.players: list[PlayerState] = []
        self.spectators: dict[str, str] = {}

        self.shapes: list = []
        self.illusions: dict[str, list] = {}
        self._hidden_from_slots: dict[int, set[int]] = {}
        self._next_shape_id = 1
        self._next_spawn_time = 0

        self._illusion_window_end: dict[str, int] = {}
        self._illusion_spawn_at: dict[str, int | None] = {}

        self.phase = WAITING_PHASE
        self.countdown_start = 0
        self.round_start = 0
        self.round_end = 0
        self.result_text = ''
        self._last_update_at = 0

        self._lock = threading.RLock()

    def add_player(self, name: str, player_id: str, now: int) -> int:
        with self._lock:
            if not self._is_joinable():
                return -1

            slot = self._lowest_free_slot()
            self.players.append(PlayerState(name, slot, player_id, now=now))
            if len(self.players) >= self.capacity:
                self._start_countdown(now)

            return slot

    def add_spectator(self, name: str, spectator_id: str) -> None:
        with self._lock:
            self.spectators[spectator_id] = name

    def remove_participant(self, participant_id: str) -> None:
        with self._lock:
            self.spectators.pop(participant_id, None)
            self.players = [
                player for player in self.players
                if player.player_id != participant_id
            ]
            self.illusions.pop(participant_id, None)
            self._illusion_window_end.pop(participant_id, None)
            self._illusion_spawn_at.pop(participant_id, None)

    def mark_disconnected(self, player_id: str) -> None:
        with self._lock:
            player = self._player_by_id(player_id)
            if player is not None:
                player.connected = False

    def is_joinable(self) -> bool:
        with self._lock:
            return self._is_joinable()

    def _is_joinable(self) -> bool:
        return (
            self.phase in (WAITING_PHASE, COUNTDOWN_PHASE) and
            len(self.players) < self.capacity
        )

    def _lowest_free_slot(self) -> int:
        taken = {player.slot for player in self.players}
        return next(slot for slot in range(self.capacity) if slot not in taken)

    def _player_by_id(self, player_id: str) -> PlayerState | None:
        for player in self.players:
            if player.player_id == player_id:
                return player

        return None

    def _connected_count(self) -> int:
        return sum(1 for player in self.players if player.connected)

    def _start_countdown(self, now: int) -> None:
        if self.phase != WAITING_PHASE:
            return

        self.phase = COUNTDOWN_PHASE
        self.countdown_start = now

    def countdown_left(self, now: int) -> int:
        elapsed = (now - self.countdown_start) // 1000
        return max(0, COUNTDOWN_SECONDS - int(elapsed))

    def seconds_left(self, now: int) -> int:
        if self.phase != PLAYING_PHASE:
            return self.duration_seconds

        return max(0, (self.round_end - now) // 1000)

    def _begin_round(self, now: int) -> None:
        self.phase = PLAYING_PHASE
        self.round_start = now
        self.round_end = now + self.duration_seconds * 1000
        self._next_spawn_time = now + 500
        self._last_update_at = now

    def update(self, now: int) -> None:
        with self._lock:
            if self.phase == COUNTDOWN_PHASE:
                if self.countdown_left(now) <= 0:
                    self._begin_round(now)
                return

            if self.phase != PLAYING_PHASE:
                return

            elapsed = max(0, now - self._last_update_at)
            self._last_update_at = now

            for player in self.players:
                player.apply_passive_changes(now)

            self._expire_shapes(now)
            self._spawn_due_shape(now)
            self._update_illusions(now, elapsed)

            if self._connected_count() < 2 or now >= self.round_end:
                self._end_match(now)

    def _expire_shapes(self, now: int) -> None:
        for shape in self.shapes:
            if shape.is_expired(now):
                self._hidden_from_slots.pop(shape.shape_id, None)

        self.shapes = [shape for shape in self.shapes if not shape.is_expired(now)]
        for player_id, owned in self.illusions.items():
            self.illusions[player_id] = [
                shape for shape in owned if not shape.is_expired(now)
            ]

    def _random_position(self) -> tuple[int, int]:
        x = random.randint(PLAY_LEFT + SHAPE_RADIUS, PLAY_LEFT + PLAY_WIDTH - SHAPE_RADIUS)
        y = random.randint(PLAY_TOP + SHAPE_RADIUS, PLAY_TOP + PLAY_HEIGHT - SHAPE_RADIUS)
        return x, y

    def _next_shape_arguments(self, now: int) -> dict:
        x, y = self._random_position()
        arguments = {
            'shape_id': self._next_shape_id,
            'x': x,
            'y': y,
            'spawn_time': now,
            'lifetime': random.randint(SHAPE_LIFETIME_MIN, SHAPE_LIFETIME_MAX),
        }
        self._next_shape_id += 1
        return arguments

    def _spawn_due_shape(self, now: int) -> None:
        if now < self._next_spawn_time:
            return

        if len(self.shapes) < MAX_SHAPES_ON_SCREEN:
            self._spawn_shape(now)

        self._next_spawn_time = now + random.randint(SHAPE_SPAWN_MIN, SHAPE_SPAWN_MAX)

    def _spawn_shape(self, now: int) -> None:
        shape_arguments = self._next_shape_arguments(now)

        category_roll = random.random()
        if category_roll < NORMAL_SHAPE_CHANCE:
            shape = NormalShape(points=random_normal_points(), **shape_arguments)
        elif category_roll < NORMAL_SHAPE_CHANCE + SHIELD_SHAPE_CHANCE:
            shape = ShieldShape(**shape_arguments)
        else:
            shape = IceShape(**shape_arguments)

        # Rolled once here, per shape and per slot, so that a shape hidden from a
        # tired player stays hidden instead of flickering at broadcast rate
        self._hidden_from_slots[shape.shape_id] = {
            slot for slot in range(self.capacity)
            if random.random() < HIDDEN_SHAPE_CHANCE
        }
        self.shapes.append(shape)

    def _update_illusions(self, now: int, elapsed: int) -> None:
        for player in self.players:
            player_id = player.player_id
            if not player.stress.sees_illusions():
                self.illusions.pop(player_id, None)
                self._illusion_window_end.pop(player_id, None)
                self._illusion_spawn_at.pop(player_id, None)
                continue

            if player.is_frozen(now):
                self._delay_illusion(player_id, elapsed)
                continue

            spawn_at = self._illusion_spawn_at.get(player_id)
            if spawn_at is not None and now >= spawn_at:
                self._illusion_spawn_at[player_id] = None
                self._spawn_illusion(player, now)

            window_end = self._illusion_window_end.get(player_id)
            if window_end is None or now >= window_end:
                interval = player.stress.illusion_interval_ms()
                self._illusion_window_end[player_id] = now + interval
                self._illusion_spawn_at[player_id] = now + random.randint(0, interval)

    def _delay_illusion(self, player_id: str, elapsed: int) -> None:
        if player_id in self._illusion_window_end:
            self._illusion_window_end[player_id] += elapsed

        spawn_at = self._illusion_spawn_at.get(player_id)
        if spawn_at is not None:
            self._illusion_spawn_at[player_id] = spawn_at + elapsed

    def _spawn_illusion(self, player: PlayerState, now: int) -> None:
        shape = IllusionShape(
            points=random_normal_points(),
            **self._next_shape_arguments(now),
        )
        self.illusions.setdefault(player.player_id, []).append(shape)

    def handle_click(self, player_id: str, x: int, y: int, now: int) -> None:
        with self._lock:
            player = self._player_by_id(player_id)
            if player is None or self.phase != PLAYING_PHASE:
                return

            if not player.register_click(now):
                return

            clicked_shape = self._find_clicked_shape(player, x, y)
            if clicked_shape is None:
                player.register_empty_click()
                return

            opponents = [other for other in self.players if other is not player]
            clicked_shape.on_click(player, opponents, now)
            self._remove_clicked_shape(player, clicked_shape)

    def _find_clicked_shape(self, player: PlayerState, x: int, y: int):
        topmost_shape = None
        for shape in self._shapes_visible_to(player):
            if not shape.contains_point(x, y):
                continue

            if topmost_shape is None or shape.spawn_time >= topmost_shape.spawn_time:
                topmost_shape = shape

        return topmost_shape

    def _remove_clicked_shape(self, player: PlayerState, clicked_shape) -> None:
        owned = self.illusions.get(player.player_id, [])
        if clicked_shape in owned:
            owned.remove(clicked_shape)
            return

        self.shapes = [
            shape for shape in self.shapes
            if shape.shape_id != clicked_shape.shape_id
        ]
        self._hidden_from_slots.pop(clicked_shape.shape_id, None)

    def _shapes_visible_to(self, player: PlayerState | None) -> list:
        if player is None:
            return list(self.shapes)

        hides = player.stamina.hides_shapes()
        visible = [
            shape for shape in self.shapes
            if not hides or player.slot not in self._hidden_from_slots.get(shape.shape_id, ())
        ]
        visible.extend(self.illusions.get(player.player_id, []))
        return visible

    def _end_match(self, now: int) -> None:
        self.phase = FINISHED_PHASE
        self.shapes.clear()
        self.illusions.clear()
        self._hidden_from_slots.clear()

        contenders = [player for player in self.players if player.connected]
        if not contenders:
            self.result_text = 'Game ended.'
            return

        top_score = max(player.score for player in contenders)
        winners = [player.name for player in contenders if player.score == top_score]
        if len(winners) > 1:
            self.result_text = 'Draw: ' + ', '.join(winners)
        else:
            self.result_text = f'{winners[0]} wins!'

    def snapshot(self, now: int, viewer_id: str | None) -> dict:
        with self._lock:
            viewer = self._player_by_id(viewer_id) if viewer_id is not None else None
            visible_shapes = [
                shape.to_dict(now) for shape in self._shapes_visible_to(viewer)
            ]

            return {
                'session_id': self.session_id,
                'phase': self.phase,
                'seconds_left': self.seconds_left(now),
                'countdown_left': self.countdown_left(now) if self.phase == COUNTDOWN_PHASE else 0,
                'capacity': self.capacity,
                'duration_seconds': self.duration_seconds,
                'players': [player.to_dict(now) for player in self.players],
                'shapes': visible_shapes,
                'spectators': list(self.spectators.values()),
                'result': self.result_text,
            }
