import argparse
import pygame
from shared.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, DEFAULT_HOST, DEFAULT_PORT,
    PLAY_LEFT, PLAY_TOP, PLAY_WIDTH, PLAY_HEIGHT, PLAYER,
    LOBBY_CAPACITY_CHOICES, DEFAULT_LOBBY_CAPACITY,
    ROUND_DURATION_CHOICES, DEFAULT_ROUND_SECONDS,
    COUNTDOWN_PHASE, PLAYING_PHASE, FINISHED_PHASE, WAITING_PHASE,
    JOINED_MSG, LOBBIES_MSG, STATE_MSG, GAME_OVER_MSG, ERROR_MSG, DISCONNECTED_MSG
)
from frontend.theme import (
    Fonts, CONNECT_SCREEN, LOBBY_SCREEN, CREATE_SCREEN, WAITING_SCREEN,
    COUNTDOWN_SCREEN, PLAYING_SCREEN, OVER_SCREEN
)
from frontend.cursor import StressCursor
from frontend.effects import Effects
from frontend.network import NetworkClient
import frontend.screens as screens
import frontend.hud as hud

CREATE_FIELDS = 2


def cycle_choice(choices, current, step):
    return choices[(choices.index(current) + step) % len(choices)]


def split_address(address: str, default_port: int) -> tuple[str, int]:
    host, _, port = address.strip().partition(':')
    if port.isdigit():
        return host or DEFAULT_HOST, int(port)
    return host or DEFAULT_HOST, default_port


class GameClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, name: str = ''):
        pygame.init()
        pygame.display.set_caption('Reaction Battle')

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()

        self.is_running = True
        self.current_screen = CONNECT_SCREEN
        self.hotspots: list = []

        self.default_port = port
        self.server_address_input = host if port == DEFAULT_PORT else f'{host}:{port}'
        self.player_name_input = name[:14]
        self.active_field = 'name'
        self.message = ''

        self.network: NetworkClient | None = None

        self.lobbies: list[dict] = []
        self.lobby_selection = 0

        self.new_lobby_capacity = DEFAULT_LOBBY_CAPACITY
        self.new_lobby_duration = DEFAULT_ROUND_SECONDS
        self.create_selection = 0

        self.session_id = ''
        self.role = PLAYER
        self.my_slot = -1
        self.state: dict = {}

        self.game_over_options = ['Back to Lobbies', 'Exit']
        self.game_over_selection = 0

        self.cursor = StressCursor(*self._play_area_centre(), 0)
        self.effects = Effects()

    def run(self) -> None:
        while self.is_running:
            self.clock.tick(FPS)
            self._pump_network()
            self._handle_events()
            self._update()
            self._draw()
            pygame.display.flip()

        self._release_mouse()
        if self.network is not None:
            self.network.leave()
            self.network.close()

        pygame.quit()

    def _play_area_centre(self) -> tuple[int, int]:
        return PLAY_LEFT + PLAY_WIDTH // 2, PLAY_TOP + PLAY_HEIGHT // 2

    def _local_player(self) -> dict | None:
        return hud.player_in_slot(self.state, self.my_slot)

    def _local_stress(self) -> float:
        player = self._local_player()
        return player.get('stress', 0.0) if player else 0.0

    def _local_player_is_frozen(self) -> bool:
        player = self._local_player()
        return bool(player.get('frozen')) if player else False

    def _set_screen(self, screen: str) -> None:
        if screen == self.current_screen:
            return

        if self.current_screen == PLAYING_SCREEN:
            self._release_mouse()

        self.current_screen = screen
        if screen == PLAYING_SCREEN:
            self.effects.reset()
            if self.role == PLAYER:
                self._grab_mouse()

    def _grab_mouse(self) -> None:
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()
        self.cursor.reset(*self._play_area_centre(), pygame.time.get_ticks())

    def _release_mouse(self) -> None:
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)

    def _pump_network(self) -> None:
        if self.network is None:
            return

        for message in self.network.drain_incoming():
            self._handle_server_message(message)

    def _handle_server_message(self, message: dict) -> None:
        message_type = message.get('type', '')

        if message_type == DISCONNECTED_MSG:
            self.network = None
            self._forget_session()
            self.message = 'Lost connection to the server.'
            self._set_screen(CONNECT_SCREEN)
        elif message_type == LOBBIES_MSG:
            self.lobbies = message.get('lobbies', [])
            if self.lobby_selection >= len(self.lobbies):
                self.lobby_selection = max(0, len(self.lobbies) - 1)
        elif message_type == JOINED_MSG:
            self.session_id = message.get('session_id', '')
            self.role = message.get('role', PLAYER)
            self.my_slot = message.get('slot', -1)
            self.message = ''
            self._set_screen(WAITING_SCREEN)
        elif message_type in (STATE_MSG, GAME_OVER_MSG):
            self._apply_session_state(message_type, message.get('state', {}))
        elif message_type == ERROR_MSG:
            self.message = message.get('reason', 'Something went wrong.')

    def _apply_session_state(self, message_type: str, state: dict) -> None:
        if not self.session_id or state.get('session_id') != self.session_id:
            return

        self.state = state
        if message_type == GAME_OVER_MSG:
            self._set_screen(OVER_SCREEN)
            return

        phase = state.get('phase', '')
        if phase == COUNTDOWN_PHASE:
            self._set_screen(COUNTDOWN_SCREEN)
        elif phase == PLAYING_PHASE:
            self._set_screen(PLAYING_SCREEN)
            self.effects.on_state(state, self.my_slot, pygame.time.get_ticks())
        elif phase == FINISHED_PHASE:
            self._set_screen(OVER_SCREEN)
        elif phase == WAITING_PHASE:
            self._set_screen(WAITING_SCREEN)

    def _forget_session(self) -> None:
        self.state = {}
        self.session_id = ''
        self.my_slot = -1
        self.role = PLAYER
        self.game_over_selection = 0

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_down(event.pos)
            elif event.type == pygame.MOUSEWHEEL and self.current_screen == LOBBY_SCREEN and self.lobbies:
                self.lobby_selection = (self.lobby_selection - event.y) % len(self.lobbies)

    def _handle_key(self, event) -> None:
        if event.key == pygame.K_ESCAPE:
            self._handle_escape()
        elif self.current_screen == CONNECT_SCREEN:
            self._handle_connect_key(event)
        elif self.current_screen == LOBBY_SCREEN:
            self._handle_lobby_key(event)
        elif self.current_screen == CREATE_SCREEN:
            self._handle_create_key(event)
        elif self.current_screen == OVER_SCREEN:
            self._handle_over_key(event)

    def _handle_escape(self) -> None:
        if self.current_screen == CONNECT_SCREEN:
            self.is_running = False
        elif self.current_screen == LOBBY_SCREEN:
            self._disconnect()
        elif self.current_screen == CREATE_SCREEN:
            self._set_screen(LOBBY_SCREEN)
        else:
            self._leave_session()

    def _handle_connect_key(self, event) -> None:
        if event.key == pygame.K_TAB:
            self.active_field = 'name' if self.active_field == 'host' else 'host'
        elif event.key == pygame.K_RETURN:
            self._do_connect()
        elif event.key == pygame.K_BACKSPACE:
            if self.active_field == 'host':
                self.server_address_input = self.server_address_input[:-1]
            else:
                self.player_name_input = self.player_name_input[:-1]
        elif event.unicode and event.unicode.isprintable():
            if self.active_field == 'host' and len(self.server_address_input) < 24:
                self.server_address_input += event.unicode
            elif self.active_field == 'name' and len(self.player_name_input) < 14:
                self.player_name_input += event.unicode

    def _handle_lobby_key(self, event) -> None:
        if event.key == pygame.K_UP and self.lobbies:
            self.lobby_selection = (self.lobby_selection - 1) % len(self.lobbies)
        elif event.key == pygame.K_DOWN and self.lobbies:
            self.lobby_selection = (self.lobby_selection + 1) % len(self.lobbies)
        elif event.key == pygame.K_r and self.network is not None:
            self.network.request_lobbies()
        elif event.key == pygame.K_n:
            self._set_screen(CREATE_SCREEN)
        elif event.key == pygame.K_RETURN:
            self._join_selected(spectator=False)
        elif event.key == pygame.K_s:
            self._join_selected(spectator=True)

    def _handle_create_key(self, event) -> None:
        if event.key == pygame.K_UP:
            self.create_selection = (self.create_selection - 1) % CREATE_FIELDS
        elif event.key == pygame.K_DOWN:
            self.create_selection = (self.create_selection + 1) % CREATE_FIELDS
        elif event.key == pygame.K_LEFT:
            self._change_new_lobby_value(self.create_selection, -1)
        elif event.key == pygame.K_RIGHT:
            self._change_new_lobby_value(self.create_selection, 1)
        elif event.key == pygame.K_RETURN:
            self._create_lobby()

    def _change_new_lobby_value(self, field: int, step: int) -> None:
        if field == 0:
            self.new_lobby_capacity = cycle_choice(
                LOBBY_CAPACITY_CHOICES, self.new_lobby_capacity, step)
        else:
            self.new_lobby_duration = cycle_choice(
                ROUND_DURATION_CHOICES, self.new_lobby_duration, step)

    def _create_lobby(self) -> None:
        if self.network is not None:
            self.network.create_lobby(
                self.player_name_input or 'Player',
                self.new_lobby_capacity,
                self.new_lobby_duration,
            )

    def _handle_over_key(self, event) -> None:
        if event.key == pygame.K_UP:
            self.game_over_selection = (self.game_over_selection - 1) % len(self.game_over_options)
        elif event.key == pygame.K_DOWN:
            self.game_over_selection = (self.game_over_selection + 1) % len(self.game_over_options)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._choose_game_over_option(self.game_over_selection)

    def _choose_game_over_option(self, index: int) -> None:
        if index == 0:
            self._leave_session()
        else:
            self.is_running = False

    def _handle_mouse_down(self, position) -> None:
        if self.current_screen == PLAYING_SCREEN:
            self._click_in_game()
            return

        for rect, action in self.hotspots:
            if rect.collidepoint(position):
                self._run_action(action)
                return

    def _run_action(self, action: tuple) -> None:
        name = action[0]
        if name == 'field':
            self.active_field = action[1]
        elif name == 'connect':
            self._do_connect()
        elif name == 'new':
            self._set_screen(CREATE_SCREEN)
        elif name == 'refresh' and self.network is not None:
            self.network.request_lobbies()
        elif name in ('join', 'spectate'):
            self.lobby_selection = action[1]
            self._join_selected(spectator=name == 'spectate')
        elif name == 'change':
            self._change_new_lobby_value(0 if action[1] == 'capacity' else 1, action[2])
        elif name == 'select':
            self.create_selection = action[1]
        elif name == 'create':
            self._create_lobby()
        elif name == 'over':
            self._choose_game_over_option(action[1])

    def _click_in_game(self) -> None:
        if self.role != PLAYER or self._local_player_is_frozen() or self.network is None:
            return

        cursor_x, cursor_y = self.cursor.position
        if self._in_play_area(cursor_x, cursor_y):
            self.network.send_click(int(cursor_x), int(cursor_y))
            self.effects.on_click(int(cursor_x), int(cursor_y), pygame.time.get_ticks())

    def _in_play_area(self, x, y) -> bool:
        return (
            PLAY_LEFT <= x <= PLAY_LEFT + PLAY_WIDTH and
            PLAY_TOP <= y <= PLAY_TOP + PLAY_HEIGHT
        )

    def _do_connect(self) -> None:
        name = self.player_name_input.strip()
        if not name:
            self.message = 'Please enter a name first.'
            return

        host, port = split_address(self.server_address_input, self.default_port)
        self.network = NetworkClient(host, port)
        if not self.network.connect():
            self.message = self.network.error
            self.network = None
            return

        self.message = ''
        self.network.request_lobbies()
        self._set_screen(LOBBY_SCREEN)

    def _join_selected(self, spectator: bool) -> None:
        if not self.lobbies or self.network is None:
            return

        lobby = self.lobbies[self.lobby_selection]
        self.network.join(self.player_name_input or 'Player', lobby['id'], spectator=spectator)

    def _leave_session(self) -> None:
        self._forget_session()
        if self.network is not None:
            self.network.leave_session()

        self._set_screen(LOBBY_SCREEN)

    def _disconnect(self) -> None:
        self._forget_session()
        if self.network is not None:
            self.network.leave()
            self.network.close()
            self.network = None

        self.lobbies = []
        self.message = ''
        self._set_screen(CONNECT_SCREEN)

    def _update(self) -> None:
        if self.current_screen != PLAYING_SCREEN or self.role != PLAYER:
            return

        delta_x, delta_y = pygame.mouse.get_rel()
        if self._local_player_is_frozen():
            return

        self.cursor.update(delta_x, delta_y, self._local_stress(), pygame.time.get_ticks())

    def _draw(self) -> None:
        now = pygame.time.get_ticks()
        mouse = pygame.mouse.get_pos()
        self.hotspots = []

        if self.current_screen == CONNECT_SCREEN:
            self.hotspots = screens.draw_connect(
                self.screen, self.fonts, self.server_address_input, self.player_name_input,
                self.active_field, self.message, mouse, now)
        elif self.current_screen == LOBBY_SCREEN:
            self.hotspots = screens.draw_lobby(
                self.screen, self.fonts, self.lobbies, self.lobby_selection, self.message, mouse)
        elif self.current_screen == CREATE_SCREEN:
            self.hotspots = screens.draw_create(
                self.screen, self.fonts, self.new_lobby_capacity, self.new_lobby_duration,
                self.create_selection, mouse)
        elif self.current_screen == WAITING_SCREEN:
            screens.draw_waiting(self.screen, self.fonts, self.session_id, self.state, now)
        elif self.current_screen == COUNTDOWN_SCREEN:
            screens.draw_countdown(self.screen, self.fonts, self.state.get('countdown_left', 0), now)
        elif self.current_screen == PLAYING_SCREEN:
            hud.draw_play(self.screen, self.fonts, self.state, self.role, self.cursor.trail_positions,
                          self.my_slot, self.effects, now)
            if self.role == PLAYER:
                hud.draw_cursor(self.screen, *self.cursor.position)
        elif self.current_screen == OVER_SCREEN:
            self.hotspots = screens.draw_over(
                self.screen, self.fonts, self.state, self.game_over_options,
                self.game_over_selection, self.my_slot, mouse)


def main() -> None:
    parser = argparse.ArgumentParser(description='Reaction Battle client')
    parser.add_argument('--host', default=DEFAULT_HOST, help='server address to fill in')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--name', default='', help='player name to fill in')
    args = parser.parse_args()

    GameClient(args.host, args.port, args.name).run()


if __name__ == '__main__':
    main()
