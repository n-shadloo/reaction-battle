from frontend.drawing import draw_text, ring
from frontend.theme import GREEN, RED

POPUP_MS = 900
RIPPLE_MS = 350
FLASH_MS = 400


class Effects:
    def __init__(self):
        self.popups: list[dict] = []
        self.ripples: list[dict] = []
        self._flash_until: dict[int, tuple[int, tuple]] = {}
        self._last_scores: dict[int, int] = {}
        self._last_click: tuple[int, int] | None = None

    def reset(self) -> None:
        self.popups.clear()
        self.ripples.clear()
        self._flash_until.clear()
        self._last_scores.clear()
        self._last_click = None

    def on_click(self, x: int, y: int, now: int) -> None:
        self._last_click = (x, y)
        self.ripples.append({'x': x, 'y': y, 'born': now})

    def on_state(self, state: dict, my_slot: int, now: int) -> None:
        for player in state.get('players', []):
            slot = player.get('slot', 0)
            score = player.get('score', 0)
            previous = self._last_scores.get(slot)
            self._last_scores[slot] = score
            if previous is None or score == previous:
                continue

            delta = score - previous
            color = GREEN if delta > 0 else RED
            self._flash_until[slot] = (now + FLASH_MS, color)

            if slot == my_slot and self._last_click is not None:
                x, y = self._last_click
                text = f'+{delta}' if delta > 0 else str(delta)
                self.popups.append({'text': text, 'x': x, 'y': y - 20, 'color': color, 'born': now})

    def card_flash(self, slot: int, now: int):
        until, color = self._flash_until.get(slot, (0, None))
        return color if now < until else None

    def draw_ripples(self, screen, now: int) -> None:
        self.ripples = [r for r in self.ripples if now - r['born'] < RIPPLE_MS]
        for ripple in self.ripples:
            t = (now - ripple['born']) / RIPPLE_MS
            shade = int(255 * (1 - t))
            ring(screen, (shade, shade, shade), (ripple['x'], ripple['y']), 8 + 30 * t, 2)

    def draw_popups(self, screen, fonts, now: int) -> None:
        self.popups = [p for p in self.popups if now - p['born'] < POPUP_MS]
        for popup in self.popups:
            t = (now - popup['born']) / POPUP_MS
            fade = 1 - t * t
            color = tuple(int(c * fade + 10 * (1 - fade)) for c in popup['color'])
            draw_text(screen, popup['text'], fonts.heading, color,
                      popup['x'], popup['y'] - 50 * t, 'center')
