import pygame
import random

pygame.init()

screen_width = 800
screen_height = 600
screen = pygame.display.set_mode((screen_width, screen_height))

clock = pygame.time.Clock()

# -------------------------
# LOAD / CREATE HIGHSCORE
# -------------------------
try:
    with open("highscore.txt", "r") as f:
        highscore = int(f.read())
except:
    highscore = 0

# Player
speed = 2
player = pygame.Rect(300, 250, 50, 50)

# Enemies
enemy_speed = 3
enemy_count = 5
spacing = 150
enemies = []

for i in range(enemy_count):
    x = random.randint(0, screen_width - 50)
    y = -i * spacing
    enemies.append(pygame.Rect(x, y, 50, 50))

# Power-up
powerup = pygame.Rect(random.randint(0, screen_width - 30),
                      random.randint(0, screen_height - 30),
                      30, 30)

powerup_active = False
powerup_timer = 0

# Score
score = 0
font = pygame.font.SysFont(None, 36)

# Timer for difficulty
start_time = pygame.time.get_ticks()

run = True
while run:

    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    keys = pygame.key.get_pressed()

    # Player movement
    if keys[pygame.K_LEFT]:
        player.x -= speed
    if keys[pygame.K_RIGHT]:
        player.x += speed
    if keys[pygame.K_UP]:
        player.y -= speed
    if keys[pygame.K_DOWN]:
        player.y += speed

    # Boundaries
    if player.x < 0:
        player.x = 0
    if player.x + player.width > screen_width:
        player.x = screen_width - player.width
    if player.y < 0:
        player.y = 0
    if player.y + player.height > screen_height:
        player.y = screen_height - player.height

    # Move enemies + respawn + scoring
    for enemy in enemies:
        enemy.y += enemy_speed

        if enemy.y > screen_height:
            enemy.x = random.randint(0, screen_width - 50)
            enemy.y = -50
            score += 1

        if player.colliderect(enemy):
            run = False

    # Power-up collision
    if player.colliderect(powerup):
        speed = 4  # boosted speed
        powerup_active = True
        powerup_timer = pygame.time.get_ticks()

        # respawn powerup
        powerup.x = random.randint(0, screen_width - 30)
        powerup.y = random.randint(0, screen_height - 30)

    # Power-up duration (5 seconds)
    if powerup_active:
        if pygame.time.get_ticks() - powerup_timer > 5000:
            speed = 2
            powerup_active = False

    # Difficulty increase every 30 seconds
    elapsed = (pygame.time.get_ticks() - start_time) // 1000
    enemy_speed = 3 + (elapsed // 30)

    # Drawing
    screen.fill((0, 0, 0))

    pygame.draw.rect(screen, (255, 0, 0), player)

    for enemy in enemies:
        pygame.draw.rect(screen, (0, 255, 0), enemy)

    pygame.draw.rect(screen, (0, 0, 255), powerup)

    score_text = font.render(f"Score: {score}", True, (255, 255, 255))
    screen.blit(score_text, (10, 10))

    highscore_text = font.render(f"Highscore: {highscore}", True, (255, 255, 255))
    screen.blit(highscore_text, (10, 40))

    pygame.display.update()

# -------------------------
# SAVE HIGHSCORE
# -------------------------
if score > highscore:
    highscore = score

with open("highscore.txt", "w") as f:
    f.write(str(highscore))

pygame.quit()






