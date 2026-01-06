import pygame
import sys
import math

pygame.init()

# ---------------------------------------------------------
# WINDOW SETTINGS
# ---------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Aqua Drift")

# ---------------------------------------------------------
# COLORS
# ---------------------------------------------------------
DARK_BLUE = (0, 50, 100)
CYAN = (80, 220, 255)

PROJECTILE_SPEED = 12
PROJECTILE_LIFE = 150
PROJECTILE_RADIUS = 6
SHOOT_FRAMES = 8

# ---------------------------------------------------------
# LEVEL LOADING
# ---------------------------------------------------------
TILE_SIZE = 32

def load_level(path):
    with open(path, "r") as f:
        return [line.rstrip("\n") for line in f.readlines()]

# Placeholder tiles
rock_tile = pygame.Surface((TILE_SIZE, TILE_SIZE))
rock_tile.fill((80, 80, 80))

coral_tile = pygame.Surface((TILE_SIZE, TILE_SIZE))
coral_tile.fill((200, 100, 150))

tile_dict = {
    "#": rock_tile,
    "~": coral_tile,
}

def build_solid_tiles(level_map):
    solid_tiles = []
    for row_index, row in enumerate(level_map):
        for col_index, tile in enumerate(row):
            if tile == "#":
                world_x = col_index * TILE_SIZE
                world_y = row_index * TILE_SIZE
                solid_tiles.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))
    return solid_tiles

# ---------------------------------------------------------
# SPRITE SHEET LOADER
# ---------------------------------------------------------
def load_sprite_sheet(path, frame_width, frame_height):
    sheet = pygame.image.load(path).convert_alpha()
    sheet_width = sheet.get_width()
    sheet_height = sheet.get_height()

    frames = []
    for y in range(0, sheet_height, frame_height):
        for x in range(0, sheet_width, frame_width):
            frame = sheet.subsurface(pygame.Rect(x, y, frame_width, frame_height))
            frames.append(frame)
    return frames

# ---------------------------------------------------------
# PLAYER
# ---------------------------------------------------------
class Player:
    def __init__(self, x, y):
        self.width = 50
        self.height = 50
        self.x = x
        self.y = y
        self.speed = 4

        # Load sprite sheet
        self.idle_frames = load_sprite_sheet("Assets/diver_sprite_sheet.png", 32, 32)

        # For now, swim uses same frames
        self.swim_frames = self.idle_frames

        # Directional versions
        self.right_idle = self.idle_frames
        self.left_idle = [pygame.transform.flip(f, True, False) for f in self.idle_frames]

        self.right_swim = self.swim_frames
        self.left_swim = [pygame.transform.flip(f, True, False) for f in self.swim_frames]

        # Animation state
        self.current_frames = self.right_idle
        self.current_frame = 0
        self.frame_timer = 0
        self.animation_speed = 0.10

        # Idle bobbing
        self.idle_timer = 0
        self.idle_offset = 0

        # Shooting
        self.shoot_timer = 0
        self.shoot_image = pygame.transform.scale(
            pygame.image.load("Assets/bubblegunmain.png").convert_alpha(),
            (32, 32)
        )

        # Bubbles + facing
        self.bubbles = []
        self.bubble_timer = 0
        self.facing = 1

        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    # -----------------------------------------------------
    # BUBBLE PARTICLES
    # -----------------------------------------------------
    def spawn_bubble(self):
        self.bubbles.append({
            "x": self.x + 20,
            "y": self.y + 40,
            "size": 4,
            "life": 30
        })

    def update_bubbles(self, screen, camera_x, camera_y):
        for bubble in self.bubbles[:]:
            bubble["y"] -= 0.5
            bubble["life"] -= 1
            bubble["size"] = max(1, bubble["size"] - 0.05)

            pygame.draw.circle(screen, (255, 240, 120),
                (int(bubble["x"] - camera_x), int(bubble["y"] - camera_y)),
                int(bubble["size"] * 2))

            pygame.draw.circle(screen, (255, 255, 150),
                (int(bubble["x"] - camera_x), int(bubble["y"] - camera_y)),
                int(bubble["size"] * 1.4))

            pygame.draw.circle(screen, (255, 255, 200),
                (int(bubble["x"] - camera_x), int(bubble["y"] - camera_y)),
                int(bubble["size"]))

            if bubble["life"] <= 0:
                self.bubbles.remove(bubble)

    # -----------------------------------------------------
    # MUZZLE POSITION
    # -----------------------------------------------------
    def muzzle(self):
        mx = self.x + (self.width if self.facing == 1 else 0)
        my = self.y + self.height * 0.6
        return mx, my

    # -----------------------------------------------------
    # MOVEMENT + ANIMATION
    # -----------------------------------------------------
    def move(self, keys, dt, solid_tiles):
        moving = False
        dx = 0
        dy = 0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= self.speed * dt
            self.facing = -1
            moving = True

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += self.speed * dt
            self.facing = 1
            moving = True

        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= self.speed * dt
            moving = True

        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += self.speed * dt
            moving = True

        self.x += dx
        self.y += dy
        self.rect.topleft = (self.x, self.y)

        # Animation switching
        if moving:
            self.current_frames = self.right_swim if self.facing == 1 else self.left_swim
            self.animation_speed = 0.25
        else:
            self.current_frames = self.right_idle if self.facing == 1 else self.left_idle
            self.animation_speed = 0.10

        if self.current_frame >= len(self.current_frames):
            self.current_frame = 0

        # Animation update
        self.frame_timer += self.animation_speed
        if self.frame_timer >= 1:
            self.frame_timer = 0
            self.current_frame = (self.current_frame + 1) % len(self.current_frames)

        # Idle bobbing
        self.idle_timer += 0.05
        self.idle_offset = math.sin(self.idle_timer) * 2

        # Bubbles
        if moving:
            self.bubble_timer += 1
            if self.bubble_timer >= 10:
                self.spawn_bubble()
                self.bubble_timer = 0

        if self.shoot_timer > 0:
            self.shoot_timer -= 1

    # -----------------------------------------------------
    # DRAW PLAYER
    # -----------------------------------------------------
    def draw(self, screen, camera_x, camera_y):
        angle = -5 if self.facing == 1 else 5

        if not self.current_frames:
            self.current_frames = self.idle_frames
            self.current_frame = 0

        if self.current_frame >= len(self.current_frames):
            self.current_frame = 0

        frame = self.current_frames[self.current_frame]
        if self.shoot_timer > 0:
            frame = self.shoot_image
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
        rotated = pygame.transform.rotate(frame, angle)

        screen.blit(
            rotated,
            (self.x - camera_x, self.y - camera_y + self.idle_offset)
        )

        self.update_bubbles(screen, camera_x, camera_y)


# ---------------------------------------------------------
# PROJECTILES
# ---------------------------------------------------------
class Projectile:
    def __init__(self, x, y, dirx, image):
        self.x = float(x)
        self.y = float(y)
        self.vx = dirx * PROJECTILE_SPEED
        self.life = PROJECTILE_LIFE
        self.image = image
        self.rect = image.get_rect(center=(int(x), int(y)))

    def update(self, solid_tiles):
        self.x += self.vx
        self.rect.centerx = int(self.x)
        self.life -= 1
        if self.life <= 0:
            return False
        for tile in solid_tiles:
            if self.rect.colliderect(tile):
                return False
        return True

    def draw(self, screen, camera_x, camera_y):
        screen.blit(self.image, (self.rect.x - camera_x, self.rect.y - camera_y))

# ---------------------------------------------------------
# DRAW LEVEL
# ---------------------------------------------------------
def draw_level(screen, level_map, camera_x, camera_y):
    spawn = None

    for row_index, row in enumerate(level_map):
        for col_index, tile in enumerate(row):
            world_x = col_index * TILE_SIZE
            world_y = row_index * TILE_SIZE

            screen_x = world_x - camera_x
            screen_y = world_y - camera_y

            if tile in tile_dict:
                screen.blit(tile_dict[tile], (screen_x, screen_y))

            if tile == "P":
                spawn = (world_x, world_y)

    return spawn

# ---------------------------------------------------------
# GAME LOOP
# ---------------------------------------------------------
def game_loop():
    clock = pygame.time.Clock()

    # Load level
    level_map = load_level("Levels/LVL1.txt")

    solid_tiles = build_solid_tiles(level_map)

    # Find spawn
    spawn = draw_level(WIN, level_map, 0, 0)
    if spawn is None:
        spawn = (WIDTH // 2, HEIGHT // 2)

    player = Player(spawn[0], spawn[1])

    bubble_img = pygame.Surface((PROJECTILE_RADIUS * 2, PROJECTILE_RADIUS * 2), pygame.SRCALPHA)
    pygame.draw.circle(bubble_img, CYAN, (PROJECTILE_RADIUS, PROJECTILE_RADIUS), PROJECTILE_RADIUS)

    projectiles = []

    camera_x = 0
    camera_y = 0

    running = True
    while running:
        dt = clock.tick(60) / 16.666

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                mx, my = player.muzzle()
                projectiles.append(Projectile(mx, my, player.facing, bubble_img))
                player.shoot_timer = SHOOT_FRAMES

        keys = pygame.key.get_pressed()
        player.move(keys, dt, solid_tiles)

        projectiles = [p for p in projectiles if p.update(solid_tiles)]

        # Camera follow
        camera_x = player.x - WIDTH // 2
        camera_y = player.y - HEIGHT // 2

        WIN.fill(DARK_BLUE)

        draw_level(WIN, level_map, camera_x, camera_y)
        for p in projectiles:
            p.draw(WIN, camera_x, camera_y)
        player.draw(WIN, camera_x, camera_y)

        pygame.display.update()

if __name__ == "__main__":
    game_loop()














