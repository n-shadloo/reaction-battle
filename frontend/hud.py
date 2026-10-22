import math
import pygame
from shared.constants import (
    PLAY_LEFT, PLAY_TOP, PLAY_WIDTH, PLAY_HEIGHT, PANEL_LEFT, PANEL_WIDTH,
    NORMAL, SHIELD, ICE, SPECTATOR, STAMINA_NEUTRAL_MIN, STAMINA_DIM_MIN, DIM_MAX_ALPHA
)
from frontend.drawing import (
    draw_text, draw_background, panel, circle, glow, bar, overlay
)
from frontend.theme import (
    SURFACE_DARK, BORDER, WHITE, MUTED, GREEN, RED, YELLOW, CYAN, ICE_BLUE,
    PURPLE, PLAYER_COLORS
)

POWER_SHAPE_COLORS = {SHIELD: CYAN, ICE: ICE_BLUE}
CURSOR_OUTLINE = [(0, 0), (0, 17), (4, 13), (7, 20), (11, 18), (8, 11), (13, 11)]

CARD_GAP = 12
CARD_MAX_HEIGHT = 140


def normal_shape_color(points) -> tuple:
    if points is None:
        return WHITE
    if points >= 3:
        return GREEN
    if points >= 1:
        return YELLOW
    return RED


def dim_alpha_for_stamina(stamina) -> int:
    if stamina >= STAMINA_NEUTRAL_MIN:
        return 0
    if stamina <= STAMINA_DIM_MIN:
        return DIM_MAX_ALPHA

    span = STAMINA_NEUTRAL_MIN - STAMINA_DIM_MIN
    return int(DIM_MAX_ALPHA * (STAMINA_NEUTRAL_MIN - stamina) / span)


def player_in_slot(state, slot):
    for player in state.get('players', []):
        if player.get('slot') == slot:
            return player
    return None


def draw_play(screen, fonts, state, role, cursor_trail, my_slot, effects, now) -> None:
    draw_background(screen)
    _draw_header(screen, fonts, state)

    area = pygame.Rect(PLAY_LEFT, PLAY_TOP, PLAY_WIDTH, PLAY_HEIGHT)
    panel(screen, area, SURFACE_DARK, BORDER, radius=16)
    _draw_grid(screen, area)

    screen.set_clip(area)
    _draw_shapes(screen, fonts, state.get('shapes', []), now)
    effects.draw_ripples(screen, now)
    _draw_trail(screen, cursor_trail)
    screen.set_clip(None)

    _draw_players(screen, fonts, state, role, my_slot, effects, now)
    _draw_local_overlays(screen, fonts, state, my_slot, now)
    effects.draw_popups(screen, fonts, now)


def _draw_header(screen, fonts, state) -> None:
    draw_text(screen, 'REACTION BATTLE', fonts.body_bold, WHITE, PLAY_LEFT + 4, 45, 'midleft')

    seconds = state.get('seconds_left', 0)
    total = max(1, state.get('duration_seconds', seconds) or 1)
    timer_rect = pygame.Rect(PLAY_LEFT + PLAY_WIDTH - 260, 37, 200, 16)
    bar(screen, timer_rect, 100 * seconds / total, RED if seconds <= 10 else CYAN)
    draw_text(screen, f'{seconds}s', fonts.body_bold, RED if seconds <= 10 else WHITE,
              PLAY_LEFT + PLAY_WIDTH, 45, 'midright')


def _draw_grid(screen, area) -> None:
    for x in range(area.x + 40, area.right, 40):
        pygame.draw.line(screen, (16, 21, 33), (x, area.y + 2), (x, area.bottom - 3))
    for y in range(area.y + 40, area.bottom, 40):
        pygame.draw.line(screen, (16, 21, 33), (area.x + 2, y), (area.right - 3, y))


def _draw_shapes(screen, fonts, shapes, now) -> None:
    for shape in shapes:
        x, y = shape.get('x', 0), shape.get('y', 0)
        radius = shape.get('radius', 30)
        kind = shape.get('kind', NORMAL)
        ratio = shape.get('lifetime_ratio', 1.0)

        if kind == NORMAL:
            points = shape.get('points', 0)
            color = normal_shape_color(points)
            label = f'+{points}' if points >= 0 else str(points)
        else:
            color = POWER_SHAPE_COLORS.get(kind, WHITE)
            label = shape.get('name', '').upper()

        # shapes about to vanish shrink a little and blink
        size = radius * (0.85 + 0.15 * min(1.0, ratio * 4))
        if ratio < 0.2 and (now // 120) % 2 == 0:
            color = tuple(int(c * 0.6) for c in color)

        glow(screen, color, (x, y), int(size * 1.9))
        circle(screen, color, (x, y), size)
        circle(screen, tuple(min(255, c + 50) for c in color), (x - size * 0.3, y - size * 0.3), size * 0.25)

        font = fonts.body_bold if kind == NORMAL else fonts.tiny
        draw_text(screen, label, font, (12, 14, 22), x, y, 'center')
        _draw_lifetime_arc(screen, x, y, size, ratio)


def _draw_lifetime_arc(screen, x, y, radius, ratio) -> None:
    if ratio <= 0:
        return

    outer = radius + 7
    box = pygame.Rect(x - outer, y - outer, outer * 2, outer * 2)
    top = math.pi / 2
    pygame.draw.arc(screen, (200, 210, 225), box, top - 2 * math.pi * ratio, top, 3)


def cursor_points(x, y) -> list:
    return [(x + offset_x, y + offset_y) for offset_x, offset_y in CURSOR_OUTLINE]


def draw_cursor(screen, x, y) -> None:
    points = cursor_points(int(x), int(y))
    pygame.draw.polygon(screen, WHITE, points)
    pygame.draw.aalines(screen, (10, 12, 18), True, points)


def _draw_trail(screen, cursor_trail) -> None:
    total = len(cursor_trail)
    for index, (trail_x, trail_y) in enumerate(cursor_trail):
        fade = 50 + int(130 * (index + 1) / total)
        pygame.draw.polygon(screen, (fade, fade, min(255, fade + 25)),
                            cursor_points(int(trail_x), int(trail_y)), 1)


def card_height(player_count) -> int:
    available = PLAY_HEIGHT - 60
    return min(CARD_MAX_HEIGHT, available // max(1, player_count) - CARD_GAP)


def card_rect(index, player_count) -> pygame.Rect:
    height = card_height(player_count)
    return pygame.Rect(PANEL_LEFT, PLAY_TOP + index * (height + CARD_GAP), PANEL_WIDTH, height)


def _draw_players(screen, fonts, state, role, my_slot, effects, now) -> None:
    players = sorted(state.get('players', []), key=lambda player: player.get('slot', 0))
    leader_score = max((player.get('score', 0) for player in players), default=0)

    for index, player in enumerate(players):
        slot = player.get('slot', 0)
        color = PLAYER_COLORS[slot % len(PLAYER_COLORS)]
        rect = card_rect(index, len(players))
        is_me = slot == my_slot

        flash = effects.card_flash(slot, now)
        border = flash if flash is not None else (color if is_me else BORDER)
        panel(screen, rect, (20, 26, 40), border, radius=14, width=2 if is_me or flash else 1)
        pygame.draw.rect(screen, color, pygame.Rect(rect.x, rect.y + 14, 4, rect.height - 28), border_radius=2)

        name = player.get('name', 'Player')
        if is_me:
            name += '  (you)'
        elif not player.get('connected', True):
            name += '  (left)'
        draw_text(screen, name, fonts.small_bold, color, rect.x + 18, rect.y + 12)

        score = player.get('score', 0)
        score_rect = draw_text(screen, str(score), fonts.heading, WHITE, rect.right - 16, rect.y + 6, 'topright')
        if score == leader_score and score > 0:
            draw_text(screen, 'LEAD', fonts.tiny, YELLOW, score_rect.left - 8, score_rect.centery, 'midright')

        bar_width = rect.width - 36 - 70
        _labeled_bar(screen, fonts, 'STAMINA', player.get('stamina', 0), GREEN,
                     rect.x + 18, rect.y + 58, bar_width)
        _labeled_bar(screen, fonts, 'STRESS', player.get('stress', 0), RED,
                     rect.x + 18, rect.y + 82, bar_width)

        badges = []
        if player.get('shielded'):
            badges.append(('SHIELD', CYAN))
        if player.get('frozen'):
            badges.append(('FROZEN', ICE_BLUE))
        if player.get('exhausted'):
            badges.append(('TIRED', RED))
        _draw_badges(screen, fonts, badges, rect.x + 18, rect.y + 104)

    footer_y = PLAY_TOP + PLAY_HEIGHT - 24
    spectators = state.get('spectators', [])
    if spectators:
        draw_text(screen, f'{len(spectators)} watching', fonts.small, MUTED, PANEL_LEFT + 4, footer_y, 'midleft')
    if role == SPECTATOR:
        draw_text(screen, 'SPECTATING', fonts.small_bold, PURPLE, PANEL_LEFT + PANEL_WIDTH, footer_y, 'midright')


def _labeled_bar(screen, fonts, label, value, color, x, y, width) -> None:
    draw_text(screen, label, fonts.tiny, MUTED, x, y + 5, 'midleft')
    bar(screen, pygame.Rect(x + 70, y, width, 10), value, color)


def _draw_badges(screen, fonts, badges, x, y) -> None:
    for text, color in badges:
        surface = fonts.tiny.render(text, True, (12, 14, 22))
        pill = pygame.Rect(x, y, surface.get_width() + 14, surface.get_height() + 4)
        pygame.draw.rect(screen, color, pill, border_radius=pill.height // 2)
        screen.blit(surface, (x + 7, y + 2))
        x = pill.right + 6


def _draw_local_overlays(screen, fonts, state, my_slot, now) -> None:
    local_player = player_in_slot(state, my_slot)
    if local_player is None:
        return

    alpha = dim_alpha_for_stamina(local_player.get('stamina', 100))
    if alpha > 0:
        overlay(screen, (0, 0, 0), alpha)

    area = pygame.Rect(PLAY_LEFT, PLAY_TOP, PLAY_WIDTH, PLAY_HEIGHT)
    if local_player.get('frozen'):
        overlay(screen, ICE_BLUE, 60, area)
        pygame.draw.rect(screen, ICE_BLUE, area, 3, border_radius=16)
        draw_text(screen, 'FROZEN', fonts.title, WHITE, area.centerx, area.centery, 'center')

    if local_player.get('exhausted'):
        pulse = 160 + int(90 * (math.sin(now / 200) + 1) / 2)
        draw_text(screen, 'EXHAUSTED  -  stop clicking to recover', fonts.body_bold, (255, pulse // 3, pulse // 3),
                  area.centerx, area.y + 40, 'center')

    if local_player.get('shielded'):
        pygame.draw.rect(screen, CYAN, area, 2, border_radius=16)

