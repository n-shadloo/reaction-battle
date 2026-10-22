from functools import lru_cache
import pygame
import pygame.gfxdraw
from frontend.theme import (
    BG_TOP, BG_BOTTOM, SURFACE, SURFACE_HOVER, BORDER, WHITE, MUTED
)


def draw_text(screen, text, font, color, x, y, anchor='topleft') -> pygame.Rect:
    surface = font.render(str(text), True, color)
    rect = surface.get_rect(**{anchor: (x, y)})
    screen.blit(surface, rect)
    return rect


@lru_cache(maxsize=4)
def _gradient(size: tuple[int, int]) -> pygame.Surface:
    width, height = size
    surface = pygame.Surface(size)
    for y in range(height):
        t = y / max(1, height - 1)
        color = [int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)]
        pygame.draw.line(surface, color, (0, y), (width, y))
    return surface


def draw_background(screen) -> None:
    screen.blit(_gradient(screen.get_size()), (0, 0))


def circle(screen, color, center, radius) -> None:
    x, y = int(center[0]), int(center[1])
    pygame.gfxdraw.filled_circle(screen, x, y, int(radius), color)
    pygame.gfxdraw.aacircle(screen, x, y, int(radius), color)


def ring(screen, color, center, radius, width) -> None:
    for offset in range(width):
        pygame.gfxdraw.aacircle(screen, int(center[0]), int(center[1]), int(radius) - offset, color)


@lru_cache(maxsize=32)
def _glow(color: tuple, radius: int) -> pygame.Surface:
    size = radius * 2
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        alpha = int(70 * (1 - r / radius) ** 2)
        pygame.gfxdraw.filled_circle(surface, radius, radius, r, (*color, alpha))
    return surface


def glow(screen, color, center, radius) -> None:
    surface = _glow(tuple(color[:3]), int(radius))
    screen.blit(surface, (int(center[0]) - radius, int(center[1]) - radius),
                special_flags=pygame.BLEND_RGBA_ADD)


def panel(screen, rect, fill=SURFACE, border=BORDER, radius=14, width=1) -> None:
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(screen, border, rect, width, border_radius=radius)


def button(screen, rect, label, font, accent, hovered=False, selected=False) -> pygame.Rect:
    active = hovered or selected
    panel(screen, rect, SURFACE_HOVER if active else SURFACE, accent if active else BORDER,
          radius=12, width=2)
    draw_text(screen, label, font, WHITE if active else MUTED, rect.centerx, rect.centery, 'center')
    return rect


def key_hint(screen, items, font, x, y) -> None:
    # items: [('ENTER', 'join'), ...], drawn centred on x as little key caps
    pieces = []
    for key, action in items:
        key_surface = font.render(key, True, WHITE)
        action_surface = font.render(action, True, MUTED)
        pieces.append((key_surface, action_surface))

    gap = 22
    total = sum(k.get_width() + 14 + 6 + a.get_width() for k, a in pieces) + gap * (len(pieces) - 1)
    cursor = x - total // 2
    for key_surface, action_surface in pieces:
        cap = pygame.Rect(cursor, y - 4, key_surface.get_width() + 14, key_surface.get_height() + 8)
        pygame.draw.rect(screen, SURFACE_HOVER, cap, border_radius=6)
        pygame.draw.rect(screen, BORDER, cap, 1, border_radius=6)
        screen.blit(key_surface, (cursor + 7, y))
        cursor = cap.right + 6
        screen.blit(action_surface, (cursor, y))
        cursor += action_surface.get_width() + gap


def bar(screen, rect, value, color, track=(12, 16, 26)) -> None:
    pygame.draw.rect(screen, track, rect, border_radius=rect.height // 2)
    filled = int(rect.width * max(0.0, min(100.0, value)) / 100)
    if filled > 0:
        pygame.draw.rect(screen, color, pygame.Rect(rect.x, rect.y, max(filled, rect.height), rect.height),
                         border_radius=rect.height // 2)


def overlay(screen, color, alpha, rect=None) -> None:
    rect = rect or screen.get_rect()
    shade = pygame.Surface(rect.size, pygame.SRCALPHA)
    shade.fill((*color, alpha))
    screen.blit(shade, rect.topleft)
