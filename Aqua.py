import pygame
import sys
import os
import math

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

        # Movement
        self.speed_x = 6.0

        # Underwater "gravity" (sink)
        self.sink_accel = 0.20
        self.max_fall = 3.0
        self.swim_up = 2.6
        self.swim_down = 2.6
        self.vy = 0.0

        # Contacts
        self.on_ground = False
        self.wall_left = False
        self.wall_right = False

        # Auto wall stick
        self.is_stuck = False
        self.stick_side = 0          # -1 left, +1 right
        self.stick_slide = 0.6       # how fast you slide down while stuck
        self.release_key = pygame.K_LSHIFT

        # Dash
        self.is_dashing = False
        self.dash_speed = 25.0
        self.dash_time = 12
        self.dash_timer = 0
        self.dash_dx = 0.0
        self.dash_dy = 0.0
        self.dash_cd = 0
        self.dash_cd_max = 18

        # Facing + "moving" state
        self.facing = 1
        self.is_moving = False

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
            raw_idle = pygame.image.load(idle_path).convert_alpha()
            raw_dash = pygame.image.load(dash_path).convert_alpha()

            self.img_idle_r = pygame.transform.scale(raw_idle, (64, 64))
            self.img_idle_l = pygame.transform.flip(self.img_idle_r, True, False)

            self.img_dash_r = pygame.transform.scale(raw_dash, (96, 96))
            self.img_dash_l = pygame.transform.flip(self.img_dash_r, True, False)
        except Exception as e:
            print("Sprite load error:", e)
            self.img_idle_r = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.img_idle_r.fill((255, 0, 0))
            self.img_idle_l = self.img_idle_r.copy()
            self.img_dash_r = pygame.transform.scale(self.img_idle_r, (96, 96))
            self.img_dash_l = pygame.transform.flip(self.img_dash_r, True, False)

        # Debug
        self.debug_mode = False

    def _resolve_axis(self, solids, move_x, move_y):
        # Reset contacts every frame
        self.wall_left = False
        self.wall_right = False

        # ---- X axis ----
        new_x = self.x + move_x
        rx = pygame.Rect(int(new_x), int(self.y), self.w, self.h)
        if move_x != 0:
            for tile in solids:
                if rx.colliderect(tile):
                    if move_x > 0:
                        rx.right = tile.left
                        self.wall_right = True
                    else:
                        rx.left = tile.right
                        self.wall_left = True
            new_x = rx.x

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

        self.on_ground = hit_floor
        if hit_floor:
            self.vy = 0.0

        self.x = float(new_x)
        self.y = float(new_y)

    def move(self, keys, solids):
        # Dash cooldown
        if self.dash_cd > 0:
            self.dash_cd -= 1

        # If stuck, SHIFT to drop OR SPACE to dash breaks stick
        if self.is_stuck and (keys[self.release_key] or keys[pygame.K_SPACE]):
            self.is_stuck = False
            self.stick_side = 0

        # Input flags (for animation + breathing)
        moving_keys = (
            keys[pygame.K_a] or keys[pygame.K_LEFT] or
            keys[pygame.K_d] or keys[pygame.K_RIGHT] or
            keys[pygame.K_w] or keys[pygame.K_UP] or
            keys[pygame.K_s] or keys[pygame.K_DOWN]
        )
        self.is_moving = bool(moving_keys) and (not self.is_stuck)

        # Horizontal input (disabled while stuck or dashing)
        dx = 0.0
        if not self.is_stuck and not self.is_dashing:
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx -= self.speed_x
                self.facing = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx += self.speed_x
                self.facing = 1

        # Underwater vertical control (disabled while dashing; overridden while stuck)
        if not self.is_dashing and not self.is_stuck:
            up = keys[pygame.K_w] or keys[pygame.K_UP]
            down = keys[pygame.K_s] or keys[pygame.K_DOWN]
            if up:
                self.vy = -self.swim_up
            elif down:
                self.vy = self.swim_down
            else:
                if not self.on_ground:
                    self.vy += self.sink_accel
                    if self.vy > self.max_fall:
                        self.vy = self.max_fall
                else:
                    self.vy = 0.0

        # Stick behavior
        if self.is_stuck and not self.is_dashing:
            dx = 0.0
            self.vy = self.stick_slide

        # Start dash
        if keys[pygame.K_SPACE] and (not self.is_dashing) and self.dash_cd <= 0:
            self.is_dashing = True
            self.dash_timer = self.dash_time
            self.dash_cd = self.dash_cd_max

            dash_dx = 0
            dash_dy = 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dash_dx = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dash_dx = 1
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                dash_dy = -1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dash_dy = 1

            if dash_dx != 0 and dash_dy != 0:
                dash_dx *= 0.707
                dash_dy *= 0.707

            # If no direction and stuck, dash away from wall
            if dash_dx == 0 and dash_dy == 0 and self.stick_side != 0:
                dash_dx = -self.stick_side

            # If still no input, dash facing direction
            if dash_dx == 0 and dash_dy == 0:
                dash_dx = self.facing

            self.dash_dx = dash_dx * self.dash_speed
            self.dash_dy = dash_dy * self.dash_speed

            # Dash breaks stick
            self.is_stuck = False
            self.stick_side = 0

        # Apply movement values
        if self.is_dashing:
            move_x = self.dash_dx
            move_y = self.dash_dy
            self.dash_timer -= 1
            if self.dash_timer <= 0:
                self.is_dashing = False
                self.dash_dx = 0.0
                self.dash_dy = 0.0
        else:
            move_x = dx
            move_y = self.vy

        # Collide (this prevents phasing through walls)
        self._resolve_axis(solids, move_x, move_y)

        # Auto-stick to walls if airborne + touching wall
        if (not self.on_ground) and (not self.is_dashing) and (not self.is_stuck):
            if self.wall_left or self.wall_right:
                self.is_stuck = True
                self.stick_side = -1 if self.wall_left else 1
                self.vy = 0.0

        # Breathing (visual only, stable)
        if (not self.is_moving) and (not self.is_dashing) and (not self.is_stuck):
            self.bob_t += 0.05
            self.bob = int(round(math.sin(self.bob_t) * 1))  # 1px
        else:
            self.bob_t = 0.0
            self.bob = 0

    def draw(self, screen, camx, camy):
        x = int(self.x - camx)
        y = int(self.y - camy + self.bob + self.feet_offset)

        # Use dash sprite for swimming OR dashing
        use_dash_sprite = self.is_dashing or self.is_moving

        if use_dash_sprite:
            img = self.img_dash_r if self.facing == 1 else self.img_dash_l
            ox = (img.get_width() - self.w) // 2
            oy = (img.get_height() - self.h) // 2
            screen.blit(img, (x - ox, y - oy))
        else:
            img = self.img_idle_r if self.facing == 1 else self.img_idle_l
            screen.blit(img, (x, y))

    def draw_debug(self, screen, font):
        if not self.debug_mode:
            return
        lines = [
            f"pos=({self.x:.1f},{self.y:.1f}) vy={self.vy:.2f}",
            f"ground={self.on_ground} stuck={self.is_stuck} side={self.stick_side}",
            f"wall L={self.wall_left} R={self.wall_right}",
            f"dashing={self.is_dashing} cd={self.dash_cd}",
            f"moving={self.is_moving}",
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
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F1:
                player.debug_mode = not player.debug_mode

        keys = pygame.key.get_pressed()
        player.move(keys, solids)

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

