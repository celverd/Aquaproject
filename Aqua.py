import pygame
import sys
import os
import math

from player_movement import MovementInput, PlayerMovement

pygame.init()

# =========================
# WINDOW / CONFIG
# =========================
WIDTH, HEIGHT = 1280, 720
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Aqua Drift")

BACKGROUND_COLOR = (10, 20, 40)
WHITE = (255, 255, 255)

TILE_SIZE = 32
FPS = 60


# =========================
# LEVEL
# =========================
def load_level(path: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, path)
    if not os.path.exists(full_path):
        return [
            "########################",
            "#......................#",
            "#......................#",
            "#..........P...........#",
            "#......................#",
            "########################"
        ]
    with open(full_path, "r") as f:
        return [line.rstrip("\n") for line in f]


def build_solid_tiles(level_map):
    solids = []
    for r, row in enumerate(level_map):
        for c, ch in enumerate(row):
            if ch == "#":
                solids.append(pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    return solids


def find_spawn(level_map):
    for r, row in enumerate(level_map):
        for c, ch in enumerate(row):
            if ch == "P":
                return c * TILE_SIZE, r * TILE_SIZE
    return WIDTH // 2, HEIGHT // 2


# =========================
# TILES
# =========================
rock_tile = pygame.Surface((TILE_SIZE, TILE_SIZE))
rock_tile.fill((80, 80, 80))


def draw_level(screen, level_map, camx, camy):
    for r, row in enumerate(level_map):
        for c, ch in enumerate(row):
            if ch == "#":
                screen.blit(rock_tile, (c * TILE_SIZE - camx, r * TILE_SIZE - camy))


# =========================
# PLAYER
# =========================
class Player:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

        # Collision box size
        self.w = 64
        self.h = 64

        # Movement (separated from rendering)
        self.movement = PlayerMovement()
        self.swim_deadzone = 0.1

        # Facing + "moving" state
        self.is_moving = False

        # Input mapping lives outside movement logic so keys are replaceable.
        self.keymap = {
            "left": [pygame.K_a, pygame.K_LEFT],
            "right": [pygame.K_d, pygame.K_RIGHT],
            "up": [pygame.K_w, pygame.K_UP],
            "down": [pygame.K_s, pygame.K_DOWN],
            "jump": [pygame.K_SPACE],
            "dash": [pygame.K_LSHIFT, pygame.K_RSHIFT],
        }
        self._prev_jump = False
        self._prev_dash = False

        # Visual: feet + breathing (visual-only, pixel-snapped)
        self.feet_offset = 6  # tweak 4..10 until feet touch
        self.bob_t = 0.0
        self.bob = 0

        # Sprites
        script_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(script_dir, "Assets")
        try:
            idle_path = os.path.join(assets_dir, "scuba.png")
            dash_path = os.path.join(assets_dir, "Dash.png")
            swim_path = os.path.join(assets_dir, "swim2.png")
            crouch_path = os.path.join(assets_dir, "wallcrouch.png")
            raw_idle = pygame.image.load(idle_path).convert_alpha()
            raw_dash = pygame.image.load(dash_path).convert_alpha()
            raw_swim = pygame.image.load(swim_path).convert_alpha()
            raw_crouch = pygame.image.load(crouch_path).convert_alpha()

            self.img_idle_r = pygame.transform.scale(raw_idle, (64, 64))
            self.img_idle_l = pygame.transform.flip(self.img_idle_r, True, False)

            self.img_dash_r = pygame.transform.scale(raw_dash, (96, 96))
            self.img_dash_l = pygame.transform.flip(self.img_dash_r, True, False)

            self.img_swim_r = pygame.transform.scale(raw_swim, (64, 64))
            self.img_swim_l = pygame.transform.flip(self.img_swim_r, True, False)

            self.img_crouch_r = pygame.transform.scale(raw_crouch, (64, 64))
            self.img_crouch_l = pygame.transform.flip(self.img_crouch_r, True, False)
        except Exception as e:
            print("Sprite load error:", e)
            self.img_idle_r = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.img_idle_r.fill((255, 0, 0))
            self.img_idle_l = self.img_idle_r.copy()
            self.img_dash_r = pygame.transform.scale(self.img_idle_r, (96, 96))
            self.img_dash_l = pygame.transform.flip(self.img_dash_r, True, False)
            self.img_swim_r = self.img_idle_r.copy()
            self.img_swim_l = self.img_idle_l.copy()
            self.img_crouch_r = self.img_idle_r.copy()
            self.img_crouch_l = self.img_idle_l.copy()

        # Debug
        self.debug_mode = False

    def _resolve_axis(self, solids, movement, move_x, move_y):
        # Reset contacts every frame
        movement.wall_left = False
        movement.wall_right = False

        # ---- X axis ----
        new_x = self.x + move_x
        rx = pygame.Rect(int(new_x), int(self.y), self.w, self.h)
        if move_x != 0:
            for tile in solids:
                if rx.colliderect(tile):
                    if move_x > 0:
                        rx.right = tile.left
                        movement.wall_right = True
                    else:
                        rx.left = tile.right
                        movement.wall_left = True
            new_x = rx.x
        else:
            for tile in solids:
                if rx.right == tile.left and rx.bottom > tile.top and rx.top < tile.bottom:
                    movement.wall_right = True
                if rx.left == tile.right and rx.bottom > tile.top and rx.top < tile.bottom:
                    movement.wall_left = True

        # ---- Y axis ----
        new_y = self.y + move_y
        ry = pygame.Rect(int(new_x), int(new_y), self.w, self.h)

        hit_floor = False
        if move_y != 0:
            for tile in solids:
                if ry.colliderect(tile):
                    if move_y > 0:
                        ry.bottom = tile.top
                        hit_floor = True
                    else:
                        ry.top = tile.bottom
                    move_y = 0.0
            new_y = ry.y
        else:
            for tile in solids:
                if ry.bottom == tile.top and ry.right > tile.left and ry.left < tile.right:
                    hit_floor = True

        movement.on_ground = hit_floor
        if hit_floor:
            movement.vy = 0.0

        self.x = float(new_x)
        self.y = float(new_y)

    def _input_pressed(self, keys, action):
        return any(keys[key] for key in self.keymap[action])

    def _read_inputs(self, keys):
        input_x = 0.0
        input_y = 0.0
        if self._input_pressed(keys, "left"):
            input_x -= 1.0
        if self._input_pressed(keys, "right"):
            input_x += 1.0
        if self._input_pressed(keys, "up"):
            input_y -= 1.0
        if self._input_pressed(keys, "down"):
            input_y += 1.0

        jump_now = self._input_pressed(keys, "jump")
        dash_now = self._input_pressed(keys, "dash")

        inputs = MovementInput(
            x=input_x,
            y=input_y,
            jump_pressed=jump_now and (not self._prev_jump),
            jump_held=jump_now,
            jump_released=(not jump_now) and self._prev_jump,
            dash_pressed=dash_now and (not self._prev_dash),
        )
        self._prev_jump = jump_now
        self._prev_dash = dash_now
        return inputs

    def move(self, keys, solids, dt):
        inputs = self._read_inputs(keys)

        # Input flags (for animation + breathing)
        moving_keys = abs(inputs.x) > self.swim_deadzone or abs(inputs.y) > self.swim_deadzone
        self.is_moving = bool(moving_keys) and (not self.movement.is_wall_crouch)

        self.movement.update(inputs, dt, solids, self._resolve_axis)

        # Breathing (visual only, stable)
        if (not self.is_moving) and (not self.movement.is_dashing) and (not self.movement.is_wall_crouch):
            self.bob_t += 0.05
            self.bob = int(round(math.sin(self.bob_t) * 1))  # 1px
        else:
            self.bob_t = 0.0
            self.bob = 0

    def draw(self, screen, camx, camy):
        x = int(self.x - camx)
        y = int(self.y - camy + self.bob + self.feet_offset)

        if self.movement.is_dashing:
            img = self.img_dash_r if self.movement.facing == 1 else self.img_dash_l
            ox = (img.get_width() - self.w) // 2
            oy = (img.get_height() - self.h) // 2
            screen.blit(img, (x - ox, y - oy))
        elif self.movement.wall_kick_timer > 0:
            img = self.img_swim_r if self.movement.facing == 1 else self.img_swim_l
            screen.blit(img, (x, y))
        elif self.movement.is_wall_crouch:
            img = self.img_crouch_r if self.movement.facing == 1 else self.img_crouch_l
            screen.blit(img, (x, y))
        elif self.movement.on_ground:
            img = self.img_idle_r if self.movement.facing == 1 else self.img_idle_l
            screen.blit(img, (x, y))
        else:
            speed = math.hypot(self.movement.vx, self.movement.vy)
            if speed > 40.0:
                img = self.img_swim_r if self.movement.facing == 1 else self.img_swim_l
            else:
                img = self.img_idle_r if self.movement.facing == 1 else self.img_idle_l
            screen.blit(img, (x, y))

    def draw_debug(self, screen, font):
        if not self.debug_mode:
            return
        state = "SWIM"
        if self.movement.is_dashing:
            state = "DASH"
        elif self.movement.wall_kick_timer > 0:
            state = "WALL_KICK"
        elif self.movement.is_wall_crouch:
            state = "WALL_CROUCH"
        lines = [
            f"state={state}",
            f"pos=({self.x:.1f},{self.y:.1f}) vx={self.movement.vx:.2f} vy={self.movement.vy:.2f}",
            f"cling_side={self.movement.stick_side}",
            f"kick_timer={self.movement.wall_kick_timer:.2f} lockout={self.movement.wall_kick_lockout:.2f}",
        ]
        bg = pygame.Surface((420, len(lines) * 20 + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        screen.blit(bg, (10, 10))
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, WHITE), (15, 15 + i * 20))


# =========================
# GAME LOOP
# =========================
def game_loop():
    clock = pygame.time.Clock()
    level_map = load_level("levels/lvl1.txt")
    solids = build_solid_tiles(level_map)
    spawn = find_spawn(level_map)

    player = Player(*spawn)
    debug_font = pygame.font.Font(None, 20)
    particles = []
    buoyancy = 0.6
    drag = 1.2

    while True:
        dt = clock.tick(FPS) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                player.debug_mode = not player.debug_mode

        keys = pygame.key.get_pressed()
        player.move(keys, solids, dt)

        for p in particles[:]:
            p["vy"] -= buoyancy * dt
            p["vx"] *= math.exp(-drag * dt)
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            if p["life"] <= 0:
                particles.remove(p)

        camx = int(round(player.x - WIDTH // 2))
        camy = int(round(player.y - HEIGHT // 2))

        WIN.fill(BACKGROUND_COLOR)
        draw_level(WIN, level_map, camx, camy)
        player.draw(WIN, camx, camy)
        player.draw_debug(WIN, debug_font)

        pygame.display.update()


if __name__ == "__main__":
    game_loop()

