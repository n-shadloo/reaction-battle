import pygame

# client screens
CONNECT_SCREEN = 'connect'
LOBBY_SCREEN = 'lobby'
CREATE_SCREEN = 'create'
WAITING_SCREEN = 'waiting'
COUNTDOWN_SCREEN = 'countdown'
PLAYING_SCREEN = 'playing'
OVER_SCREEN = 'over'

# colors
BG_TOP = (14, 18, 30)
BG_BOTTOM = (6, 8, 14)
SURFACE = (22, 28, 42)
SURFACE_HOVER = (30, 38, 56)
SURFACE_DARK = (9, 12, 20)
BORDER = (44, 54, 76)
WHITE = (236, 240, 246)
MUTED = (128, 140, 162)
FAINT = (70, 80, 100)
GREEN = (72, 214, 120)
BLUE = (88, 150, 255)
RED = (255, 84, 96)
YELLOW = (255, 204, 77)
PURPLE = (178, 110, 255)
ORANGE = (255, 150, 64)
CYAN = (64, 224, 230)
PINK = (255, 112, 180)
ICE_BLUE = (140, 200, 255)

# each player's color, by slot
PLAYER_COLORS = [BLUE, ORANGE, PURPLE, PINK]

FONT_NAMES = 'avenirnext,segoeui,helveticaneue,arial'


class Fonts:
    def __init__(self):
        self.title = pygame.font.SysFont(FONT_NAMES, 68, bold=True)
        self.heading = pygame.font.SysFont(FONT_NAMES, 36, bold=True)
        self.body = pygame.font.SysFont(FONT_NAMES, 24)
        self.body_bold = pygame.font.SysFont(FONT_NAMES, 24, bold=True)
        self.small = pygame.font.SysFont(FONT_NAMES, 18)
        self.small_bold = pygame.font.SysFont(FONT_NAMES, 18, bold=True)
        self.tiny = pygame.font.SysFont(FONT_NAMES, 14, bold=True)
        self.countdown = pygame.font.SysFont(FONT_NAMES, 180, bold=True)
