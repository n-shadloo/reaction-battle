import math
import pygame
from shared.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from frontend.drawing import (
    draw_text, draw_background, panel, button, key_hint, circle, glow
)
from frontend.theme import (
    SURFACE, SURFACE_HOVER, BORDER, WHITE, MUTED, FAINT, GREEN, RED, YELLOW,
    CYAN, PURPLE, PLAYER_COLORS
)

CENTER_X = SCREEN_WIDTH // 2

# every draw function returns hotspots: a list of (rect, action) the client can click


def _logo(screen, fonts, y, now) -> None:
    pulse = (math.sin(now / 500) + 1) / 2
    for index, color in enumerate(PLAYER_COLORS):
        x = CENTER_X - 75 + index * 50
        glow(screen, color, (x, y), 26 + int(4 * pulse))
        circle(screen, color, (x, y), 11)


def _input(screen, fonts, label, value, active, rect, now) -> None:
    draw_text(screen, label, fonts.small, MUTED, rect.x + 2, rect.y - 26)
    panel(screen, rect, SURFACE_HOVER if active else SURFACE, CYAN if active else BORDER,
          radius=12, width=2)
    text_rect = draw_text(screen, value, fonts.body, WHITE, rect.x + 16, rect.centery, 'midleft')
    if active and (now // 500) % 2 == 0:
        pygame.draw.line(screen, CYAN, (text_rect.right + 3, rect.centery - 13),
                         (text_rect.right + 3, rect.centery + 13), 2)


def draw_connect(screen, fonts, server_address, player_name, active_field,
                 message, mouse, now) -> list:
    draw_background(screen)
    _logo(screen, fonts, 92, now)
    draw_text(screen, 'REACTION BATTLE', fonts.title, WHITE, CENTER_X, 170, 'center')
    draw_text(screen, 'Click the shapes faster than your rivals', fonts.body, MUTED,
              CENTER_X, 222, 'center')

    host_rect = pygame.Rect(CENTER_X - 210, 310, 420, 54)
    name_rect = pygame.Rect(CENTER_X - 210, 410, 420, 54)
    _input(screen, fonts, 'Server address', server_address, active_field == 'host', host_rect, now)
    _input(screen, fonts, 'Your name', player_name, active_field == 'name', name_rect, now)

    connect_rect = pygame.Rect(CENTER_X - 130, 500, 260, 56)
    button(screen, connect_rect, 'Connect', fonts.body_bold, GREEN,
           hovered=connect_rect.collidepoint(mouse))

    key_hint(screen, [('TAB', 'switch field'), ('ENTER', 'connect'), ('ESC', 'quit')],
             fonts.small, CENTER_X, 600)

    if message:
        draw_text(screen, message, fonts.small, RED, CENTER_X, 650, 'center')

    return [(host_rect, ('field', 'host')), (name_rect, ('field', 'name')),
            (connect_rect, ('connect',))]


def draw_lobby(screen, fonts, lobbies, selection, message, mouse) -> list:
    draw_background(screen)
    draw_text(screen, 'Lobbies', fonts.heading, WHITE, 60, 50)
    draw_text(screen, f'{len(lobbies)} open', fonts.small, MUTED, 62, 98)
    hotspots = []

    new_rect = pygame.Rect(SCREEN_WIDTH - 230, 52, 170, 48)
    refresh_rect = pygame.Rect(SCREEN_WIDTH - 360, 52, 116, 48)
    button(screen, new_rect, '+  New lobby', fonts.small_bold, GREEN, new_rect.collidepoint(mouse))
    button(screen, refresh_rect, 'Refresh', fonts.small_bold, CYAN, refresh_rect.collidepoint(mouse))
    hotspots += [(new_rect, ('new',)), (refresh_rect, ('refresh',))]

    if not lobbies:
        box = pygame.Rect(60, 150, SCREEN_WIDTH - 120, 360)
        panel(screen, box, SURFACE, BORDER)
        draw_text(screen, 'No open lobbies right now', fonts.body_bold, WHITE,
                  box.centerx, box.centery - 18, 'center')
        draw_text(screen, 'Create one and share the code with your friends.', fonts.small, MUTED,
                  box.centerx, box.centery + 18, 'center')
    else:
        y = 150
        for index, lobby in enumerate(lobbies[:6]):
            row = pygame.Rect(60, y, SCREEN_WIDTH - 120, 66)
            hovered = row.collidepoint(mouse)
            selected = index == selection
            panel(screen, row, SURFACE_HOVER if hovered or selected else SURFACE,
                  YELLOW if selected else BORDER, radius=12, width=2 if selected else 1)

            players, capacity = lobby.get('players', 0), lobby.get('capacity', 0)
            draw_text(screen, f"#{lobby.get('id', '')}", fonts.body_bold, YELLOW if selected else WHITE,
                      row.x + 22, row.centery, 'midleft')
            draw_text(screen, f"hosted by {lobby.get('host', '')}", fonts.small, MUTED,
                      row.x + 160, row.centery, 'midleft')
            draw_text(screen, f"{lobby.get('duration_seconds', 0)}s round", fonts.small, MUTED,
                      row.x + 420, row.centery, 'midleft')

            for seat in range(capacity):
                color = PLAYER_COLORS[seat % len(PLAYER_COLORS)] if seat < players else FAINT
                circle(screen, color, (row.x + 560 + seat * 22, row.centery), 7)

            watch_rect = pygame.Rect(row.right - 120, row.y + 14, 100, 38)
            button(screen, watch_rect, 'Watch', fonts.small, PURPLE, watch_rect.collidepoint(mouse))
            hotspots.append((watch_rect, ('spectate', index)))
            hotspots.append((row, ('join', index)))
            y += 78

    key_hint(screen, [('ENTER', 'join'), ('S', 'watch'), ('N', 'new lobby'), ('R', 'refresh'),
                      ('ESC', 'disconnect')], fonts.small, CENTER_X, SCREEN_HEIGHT - 70)

    if message:
        draw_text(screen, message, fonts.small, RED, CENTER_X, SCREEN_HEIGHT - 110, 'center')

    return hotspots


def draw_create(screen, fonts, capacity, duration_seconds, selection, mouse) -> list:
    draw_background(screen)
    draw_text(screen, 'New lobby', fonts.heading, WHITE, CENTER_X, 120, 'center')
    hotspots = []

    rows = (('Players', f'{capacity}', 'capacity'), ('Round length', f'{duration_seconds}s', 'duration'))
    y = 220
    for index, (label, value, field) in enumerate(rows):
        selected = index == selection
        box = pygame.Rect(CENTER_X - 240, y, 480, 76)
        panel(screen, box, SURFACE_HOVER if selected else SURFACE, CYAN if selected else BORDER,
              radius=14, width=2)
        draw_text(screen, label, fonts.body, MUTED, box.x + 24, box.centery, 'midleft')

        left = pygame.Rect(box.right - 200, box.centery - 20, 40, 40)
        right = pygame.Rect(box.right - 64, box.centery - 20, 40, 40)
        for arrow, text in ((left, '<'), (right, '>')):
            button(screen, arrow, text, fonts.body_bold, CYAN, arrow.collidepoint(mouse))
        draw_text(screen, value, fonts.body_bold, YELLOW if selected else WHITE,
                  (left.right + right.left) // 2, box.centery, 'center')

        hotspots += [(left, ('change', field, -1)), (right, ('change', field, 1)),
                     (box, ('select', index))]
        y += 100

    create_rect = pygame.Rect(CENTER_X - 130, 450, 260, 56)
    button(screen, create_rect, 'Create lobby', fonts.body_bold, GREEN, create_rect.collidepoint(mouse))
    hotspots.insert(0, (create_rect, ('create',)))

    key_hint(screen, [('UP/DOWN', 'field'), ('LEFT/RIGHT', 'change'), ('ENTER', 'create'),
                      ('ESC', 'back')], fonts.small, CENTER_X, 560)
    return hotspots


def draw_waiting(screen, fonts, session_id, state, now) -> list:
    draw_background(screen)
    draw_text(screen, 'Waiting for players', fonts.heading, WHITE, CENTER_X, 150, 'center')

    code_box = pygame.Rect(CENTER_X - 150, 200, 300, 70)
    panel(screen, code_box, SURFACE, BORDER)
    draw_text(screen, 'LOBBY CODE', fonts.tiny, MUTED, code_box.centerx, code_box.y + 16, 'center')
    draw_text(screen, session_id, fonts.body_bold, YELLOW, code_box.centerx, code_box.y + 44, 'center')

    players = state.get('players', [])
    capacity = state.get('capacity', 0)
    spacing = 150
    start_x = CENTER_X - spacing * (capacity - 1) // 2
    for seat in range(capacity):
        x = start_x + seat * spacing
        player = next((p for p in players if p.get('slot') == seat), None)
        color = PLAYER_COLORS[seat % len(PLAYER_COLORS)]
        if player is not None:
            glow(screen, color, (x, 380), 60)
            circle(screen, color, (x, 380), 30)
            draw_text(screen, player.get('name', 'Player'), fonts.small_bold, WHITE, x, 432, 'center')
        else:
            bob = int(4 * math.sin(now / 300 + seat))
            pygame.draw.circle(screen, FAINT, (x, 380 + bob), 30, 2)
            draw_text(screen, 'waiting...', fonts.small, FAINT, x, 432, 'center')

    draw_text(screen, f'{len(players)}/{capacity} joined', fonts.body, MUTED, CENTER_X, 500, 'center')
    key_hint(screen, [('ESC', 'leave lobby')], fonts.small, CENTER_X, 580)
    return []


def draw_countdown(screen, fonts, number, now) -> list:
    draw_background(screen)
    shown = str(number) if number > 0 else 'GO!'
    color = YELLOW if number > 0 else GREEN

    # each second the number shrinks from big to normal size
    phase = (now % 1000) / 1000
    scale = 1.6 - 0.6 * min(1.0, phase * 3)
    surface = fonts.countdown.render(shown, True, WHITE)
    size = (int(surface.get_width() * scale), int(surface.get_height() * scale))
    surface = pygame.transform.smoothscale(surface, size)

    center = (CENTER_X, SCREEN_HEIGHT // 2)
    box = pygame.Rect(0, 0, 300, 300)
    box.center = center
    pygame.draw.circle(screen, SURFACE, center, 150, 10)
    pygame.draw.arc(screen, color, box, math.pi / 2, math.pi / 2 + 2 * math.pi * (1 - phase), 10)
    screen.blit(surface, surface.get_rect(center=center))
    draw_text(screen, 'Get ready', fonts.body, MUTED, CENTER_X, SCREEN_HEIGHT // 2 + 195, 'center')
    return []


def draw_over(screen, fonts, state, options, selection, my_slot, mouse) -> list:
    draw_background(screen)
    draw_text(screen, 'GAME OVER', fonts.title, WHITE, CENTER_X, 90, 'center')
    draw_text(screen, state.get('result', ''), fonts.body_bold, YELLOW, CENTER_X, 150, 'center')

    ranked = sorted(state.get('players', []), key=lambda player: player.get('score', 0), reverse=True)
    y = 200
    for index, player in enumerate(ranked):
        slot = player.get('slot', 0)
        color = PLAYER_COLORS[slot % len(PLAYER_COLORS)]
        row = pygame.Rect(CENTER_X - 260, y, 520, 58)
        panel(screen, row, SURFACE, color if index == 0 else BORDER, radius=12, width=2 if index == 0 else 1)

        place_color = YELLOW if index == 0 else MUTED
        draw_text(screen, f'#{index + 1}', fonts.body_bold, place_color, row.x + 22, row.centery, 'midleft')
        circle(screen, color, (row.x + 90, row.centery), 9)

        name = player.get('name', 'Player')
        if slot == my_slot:
            name += '  (you)'
        if not player.get('connected', True):
            name += '  (left)'
        draw_text(screen, name, fonts.body, WHITE, row.x + 112, row.centery, 'midleft')
        draw_text(screen, str(player.get('score', 0)), fonts.body_bold, WHITE,
                  row.right - 24, row.centery, 'midright')
        y += 68

    hotspots = []
    for index, option in enumerate(options):
        rect = pygame.Rect(CENTER_X - 130, 500 + index * 70, 260, 54)
        button(screen, rect, option, fonts.body_bold, GREEN if index == 0 else RED,
               hovered=rect.collidepoint(mouse), selected=index == selection)
        hotspots.append((rect, ('over', index)))
    return hotspots
