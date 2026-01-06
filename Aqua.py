import pygame
import sys
import os
import math

from player_animator import (
    HURT_DURATION,
    SHOOT_DURATION,
    build_default_player_animator,
)
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

        # Movement (px/sec, px/sec^2)
        self.accel = 900.0
        self.drag = 2.6
        self.max_speed = 220.0
        self.sink_accel = 120.0
        self.vx = 0.0
        self.vy = 0.0
        self.swim_deadzone = 0.1

        # Contacts
        self.on_ground = False
        self.wall_left = False
        self.wall_right = False

        # Wall crouch / kick
        self.is_wall_crouch = False
        self.stick_side = 0          # -1 left, +1 right
        self.stick_slide = 24.0
        self.wall_kick_timer = 0.0
        self.wall_kick_duration = 0.18
        self.wall_kick_lockout = 0.0
        self.wall_kick_lockout_max = 0.25
        self.wall_kick_speed_x = 260.0
        self.wall_kick_speed_y = 180.0

        # Dash
        self.is_dashing = False
        self.dash_speed = 420.0
        self.dash_time = 0.18
        self.dash_timer = 0.0
        self.dash_dx = 0.0
        self.dash_dy = 0.0
        self.dash_cd = 0.0
        self.dash_cd_max = 0.3

        # Facing + "moving" state
        self.facing = 1
        self.is_moving = False
        self.shoot_timer = 0.0
        self.hurt_timer = 0.0

        # Visual: feet + breathing (visual-only, pixel-snapped)
        self.feet_offset = 6  # tweak 4..10 until feet touch
        self.bob_t = 0.0
        self.bob = 0

        # Animator (loads all frames once)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.animator = build_default_player_animator(script_dir)
        self.anim_state = "idle"
        self.anim_frame = None
        self.anim_offset = (0, 0)

        # Debug
        self.debug_mode = False

    def trigger_shoot(self):
        self.shoot_timer = SHOOT_DURATION

    def trigger_hurt(self):
        self.hurt_timer = HURT_DURATION

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
        else:
            for tile in solids:
                if rx.right == tile.left and rx.bottom > tile.top and rx.top < tile.bottom:
                    self.wall_right = True
                if rx.left == tile.right and rx.bottom > tile.top and rx.top < tile.bottom:
                    self.wall_left = True

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

        self.on_ground = hit_floor
        if hit_floor:
            self.vy = 0.0

        self.x = float(new_x)
        self.y = float(new_y)

    def move(self, keys, solids, dt):
        # Timers
        if self.dash_cd > 0:
            self.dash_cd = max(0.0, self.dash_cd - dt)
        if self.wall_kick_timer > 0:
            self.wall_kick_timer = max(0.0, self.wall_kick_timer - dt)
        if self.wall_kick_lockout > 0:
            self.wall_kick_lockout = max(0.0, self.wall_kick_lockout - dt)
        if self.shoot_timer > 0:
            self.shoot_timer = max(0.0, self.shoot_timer - dt)
        if self.hurt_timer > 0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)

        # Input flags (for animation + breathing)
        moving_keys = (
            keys[pygame.K_a] or keys[pygame.K_LEFT] or
            keys[pygame.K_d] or keys[pygame.K_RIGHT] or
            keys[pygame.K_w] or keys[pygame.K_UP] or
            keys[pygame.K_s] or keys[pygame.K_DOWN]
        )
        self.is_moving = bool(moving_keys) and (not self.is_wall_crouch)

        input_x = 0.0
        input_y = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            input_x -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            input_x += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            input_y -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            input_y += 1.0

        if abs(input_x) > self.swim_deadzone:
            self.facing = 1 if input_x > 0 else -1

        # Start dash
        if keys[pygame.K_SPACE] and (not self.is_dashing) and self.dash_cd <= 0 and (not self.is_wall_crouch):
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

            # If still no input, dash facing direction
            if dash_dx == 0 and dash_dy == 0:
                dash_dx = self.facing

            self.dash_dx = dash_dx * self.dash_speed
            self.dash_dy = dash_dy * self.dash_speed
            self.vx = self.dash_dx
            self.vy = self.dash_dy

        # Wall kick (SPACE while clinging)
        if self.is_wall_crouch and keys[pygame.K_SPACE] and self.wall_kick_lockout <= 0:
            self.is_wall_crouch = False
            self.wall_kick_timer = self.wall_kick_duration
            self.wall_kick_lockout = self.wall_kick_lockout_max
            kick_dir = -self.stick_side if self.stick_side != 0 else -self.facing
            self.vx = kick_dir * self.wall_kick_speed_x
            self.vy = -self.wall_kick_speed_y
            self.stick_side = 0

        # Movement update
        if self.is_dashing:
            move_x = self.dash_dx * dt
            move_y = self.dash_dy * dt
            self.dash_timer -= dt
            if self.dash_timer <= 0:
                self.is_dashing = False
        elif self.is_wall_crouch:
            move_x = 0.0
            self.vx = 0.0
            if input_y < 0:
                self.vy = -self.stick_slide
            elif input_y > 0:
                self.vy = self.stick_slide
            else:
                self.vy = self.stick_slide * 0.4
            move_y = self.vy * dt
        else:
            self.vx += input_x * self.accel * dt
            self.vy += input_y * self.accel * dt
            if not self.on_ground:
                self.vy += self.sink_accel * dt
            else:
                self.vy = min(self.vy, 0.0)

            self.vx -= self.drag * self.vx * dt
            self.vy -= self.drag * self.vy * dt

            speed = math.hypot(self.vx, self.vy)
            if speed > self.max_speed:
                scale = self.max_speed / speed
                self.vx *= scale
                self.vy *= scale

            move_x = self.vx * dt
            move_y = self.vy * dt

        # Collide (this prevents phasing through walls)
        self._resolve_axis(solids, move_x, move_y)

        # Auto-stick to walls if airborne + touching wall
        if (not self.on_ground) and (not self.is_dashing) and (not self.is_wall_crouch) and self.wall_kick_lockout <= 0:
            if self.wall_left or self.wall_right:
                self.is_wall_crouch = True
                self.stick_side = -1 if self.wall_left else 1
                self.facing = -self.stick_side
                self.vx = 0.0
                self.vy = 0.0

        if self.is_wall_crouch and (not self.wall_left) and (not self.wall_right):
            self.is_wall_crouch = False
            self.stick_side = 0

        # Breathing (visual only, stable)
        if (not self.is_moving) and (not self.is_dashing) and (not self.is_wall_crouch):
            self.bob_t += 0.05
            self.bob = int(round(math.sin(self.bob_t) * 1))  # 1px
        else:
            self.bob_t = 0.0
            self.bob = 0

        # Feed animator a read-only snapshot so gameplay stays separate.
        snapshot = {
            "vx": self.vx,
            "vy": self.vy,
            "on_ground": self.on_ground,
            "is_shooting": self.shoot_timer > 0.0,
            "is_dashing": self.is_dashing,
            "is_hurt": self.hurt_timer > 0.0,
            "facing_dir": self.facing,
        }
        self.anim_frame, self.anim_offset, self.anim_state = self.animator.update(dt, snapshot)

    def draw(self, screen, camx, camy):
        x = int(self.x - camx)
        y = int(self.y - camy + self.bob + self.feet_offset)

        if self.anim_frame is not None:
            screen.blit(self.anim_frame, (x - self.anim_offset[0], y - self.anim_offset[1]))

    def draw_debug(self, screen, font):
        if not self.debug_mode:
            return
        lines = [
            f"state={self.anim_state}",
            f"pos=({self.x:.1f},{self.y:.1f}) vx={self.vx:.2f} vy={self.vy:.2f}",
            f"cling_side={self.stick_side}",
            f"kick_timer={self.wall_kick_timer:.2f} lockout={self.wall_kick_lockout:.2f}",
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
            if e.type == pygame.KEYDOWN and e.key == pygame.K_LCTRL:
                player.trigger_shoot()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_h:
                player.trigger_hurt()

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

