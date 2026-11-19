"""ROACH SMASH! Basic game with mouse-simulated swatting.

Run: python main.py

Fast pointer movement across a roach counts as a swing. Hovering does not.
Camera tracking is not connected in this version.
"""

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path

import pygame


WIDTH = 960
HEIGHT = 540
FPS = 60

GAME_SECONDS = 60.0
STARTING_LIVES = 3
ROACH_RADIUS = 24
POINTER_RADIUS = 10

MIN_SWING_SPEED = 850.0
HIT_COOLDOWN = 0.30
MAX_SAMPLE_GAP = 0.15
SPAWN_INTERVAL = 1.4
MAX_ROACHES = 7

SPLAT_DURATION = 0.45
HIGH_SCORE_FILE = Path(__file__).resolve().parent / "high_score.json"

BACKGROUND = (28, 22, 46)
PLAY_AREA = (43, 37, 61)
WHITE = (245, 245, 245)
YELLOW = (255, 218, 75)
GREEN = (100, 255, 130)
RED = (255, 105, 115)
BROWN = (181, 92, 55)
DARK_BROWN = (50, 26, 29)
BUTTON = (83, 138, 97)

PLAY_TOP = 100
PLAY_BOTTOM = HEIGHT - 55


@dataclass
class Roach:
    x: float
    y: float
    vx: float
    vy: float
    golden: bool = False

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt

    def escaped(self):
        margin = ROACH_RADIUS + 12
        return (
            self.x < -margin
            or self.x > WIDTH + margin
            or self.y < PLAY_TOP - margin
            or self.y > PLAY_BOTTOM + margin
        )


@dataclass
class Splat:
    x: int
    y: int
    golden: bool
    started_at: float


def load_high_score():
    """Load the saved high score, returning zero if the file is unavailable."""
    try:
        with HIGH_SCORE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        value = data.get("high_score", 0)
        if type(value) is int and value >= 0:
            return value

    except (OSError, ValueError, TypeError, AttributeError):
        pass

    return 0


def save_high_score(value):
    """Save the high score without crashing if the drive is not writable."""
    try:
        with HIGH_SCORE_FILE.open("w", encoding="utf-8") as file:
            json.dump({"high_score": value}, file)
    except OSError as error:
        print(f"Could not save high score: {error}")


def point_to_segment_distance(point, start, end):
    """Shortest distance from a point to a pointer-movement trajectory."""
    px, py = point
    ax, ay = start
    bx, by = end

    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy

    if length_squared == 0:
        return math.hypot(px - ax, py - ay)

    amount = ((px - ax) * dx + (py - ay) * dy) / length_squared
    amount = max(0.0, min(1.0, amount))

    nearest_x = ax + amount * dx
    nearest_y = ay + amount * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def spawn_roach():
    """Spawn outside one edge and crawl across the play area."""
    edge = random.choice(("left", "right", "top", "bottom"))
    speed = random.uniform(75, 145)
    golden = random.random() < 0.15

    if edge == "left":
        return Roach(
            -ROACH_RADIUS,
            random.uniform(PLAY_TOP + 40, PLAY_BOTTOM - 40),
            speed,
            random.uniform(-22, 22),
            golden,
        )

    if edge == "right":
        return Roach(
            WIDTH + ROACH_RADIUS,
            random.uniform(PLAY_TOP + 40, PLAY_BOTTOM - 40),
            -speed,
            random.uniform(-22, 22),
            golden,
        )

    if edge == "top":
        return Roach(
            random.uniform(60, WIDTH - 60),
            PLAY_TOP - ROACH_RADIUS,
            random.uniform(-22, 22),
            speed,
            golden,
        )

    return Roach(
        random.uniform(60, WIDTH - 60),
        PLAY_BOTTOM + ROACH_RADIUS,
        random.uniform(-22, 22),
        -speed,
        golden,
    )


def draw_centered(screen, font, text, y, color=WHITE):
    image = font.render(text, True, color)
    screen.blit(image, ((WIDTH - image.get_width()) // 2, y))


def draw_roach(screen, roach):
    x = int(roach.x)
    y = int(roach.y)
    color = YELLOW if roach.golden else BROWN

    for offset in (-12, 0, 12):
        pygame.draw.line(
            screen,
            DARK_BROWN,
            (x - 15, y + offset // 2),
            (x - 31, y + offset),
            4,
        )
        pygame.draw.line(
            screen,
            DARK_BROWN,
            (x + 15, y + offset // 2),
            (x + 31, y + offset),
            4,
        )

    pygame.draw.line(
        screen, DARK_BROWN, (x - 8, y - 15), (x - 19, y - 32), 3
    )
    pygame.draw.line(
        screen, DARK_BROWN, (x + 8, y - 15), (x + 19, y - 32), 3
    )

    pygame.draw.ellipse(
        screen,
        DARK_BROWN,
        (
            x - ROACH_RADIUS,
            y - ROACH_RADIUS + 2,
            ROACH_RADIUS * 2,
            ROACH_RADIUS * 2 - 4,
        ),
    )
    pygame.draw.ellipse(screen, color, (x - 19, y - 19, 38, 38))
    pygame.draw.circle(screen, WHITE, (x - 8, y - 7), 4)
    pygame.draw.circle(screen, WHITE, (x + 8, y - 7), 4)


def draw_splat(screen, splat, now):
    """Draw an expanding impact ring and shrinking paint droplets."""
    progress = (now - splat.started_at) / SPLAT_DURATION
    if not 0 <= progress < 1:
        return

    color = YELLOW if splat.golden else RED
    center = (splat.x, splat.y)

    ring_radius = int(20 + 55 * progress)
    ring_width = max(1, int(6 * (1 - progress)))
    pygame.draw.circle(screen, color, center, ring_radius, ring_width)

    droplet_radius = max(1, int(9 * (1 - progress)))
    directions = (
        (-1.0, 0.0),
        (1.0, 0.0),
        (0.0, -1.0),
        (0.0, 1.0),
        (-0.7, -0.7),
        (0.7, -0.7),
        (-0.7, 0.7),
        (0.7, 0.7),
    )

    for dx, dy in directions:
        distance = 12 + 35 * progress
        position = (
            int(splat.x + dx * distance),
            int(splat.y + dy * distance),
        )
        pygame.draw.circle(screen, color, position, droplet_radius)

    pygame.draw.circle(
        screen,
        color,
        center,
        max(2, int(15 * (1 - progress))),
    )


def main():
    pygame.init()

    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("ROACH SMASH! - Basic Game")
        clock = pygame.time.Clock()

        title_font = pygame.font.SysFont("arial", 58, bold=True)
        heading_font = pygame.font.SysFont("arial", 40, bold=True)
        text_font = pygame.font.SysFont("arial", 27)
        small_font = pygame.font.SysFont("arial", 21)

        button_rect = pygame.Rect(WIDTH // 2 - 145, 335, 290, 70)

        state = "start"
        score = 0
        lives = STARTING_LIVES
        eliminated = 0
        high_score = load_high_score()
        roaches = []
        splats = []
        time_left = GAME_SECONDS
        spawn_elapsed = 0.0

        pointer = pygame.mouse.get_pos()
        previous_pointer = pointer
        previous_sample_time = time.perf_counter()
        pointer_speed = 0.0
        swing_armed = True
        last_hit_time = -HIT_COOLDOWN

        feedback_text = ""
        feedback_position = (0, 0)
        feedback_until = 0.0

        def start_game(now):
            nonlocal state, score, lives, eliminated, roaches, splats
            nonlocal time_left, spawn_elapsed, previous_pointer
            nonlocal previous_sample_time, pointer_speed
            nonlocal swing_armed, last_hit_time, feedback_until

            state = "playing"
            score = 0
            lives = STARTING_LIVES
            eliminated = 0
            roaches = [spawn_roach()]
            splats = []
            time_left = GAME_SECONDS
            spawn_elapsed = 0.0

            previous_pointer = pygame.mouse.get_pos()
            previous_sample_time = now
            pointer_speed = 0.0
            swing_armed = True
            last_hit_time = -HIT_COOLDOWN
            feedback_until = 0.0

        running = True

        while running:
            # Limit simulation movement after a delayed remote-desktop frame.
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            now = time.perf_counter()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if state != "playing":
                            start_game(now)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and state != "playing":
                        if button_rect.collidepoint(event.pos):
                            start_game(now)

            pointer = pygame.mouse.get_pos()
            elapsed = now - previous_sample_time
            valid_sample = 0 < elapsed <= MAX_SAMPLE_GAP

            if valid_sample:
                pointer_speed = (
                    math.dist(previous_pointer, pointer) / elapsed
                )
                if pointer_speed < MIN_SWING_SPEED:
                    swing_armed = True
            else:
                pointer_speed = 0.0
                swing_armed = True

            if state == "playing":
                time_left = max(0.0, time_left - dt)
                spawn_elapsed += dt

                if spawn_elapsed >= SPAWN_INTERVAL:
                    spawn_elapsed -= SPAWN_INTERVAL
                    if len(roaches) < MAX_ROACHES:
                        roaches.append(spawn_roach())

                for roach in roaches[:]:
                    roach.update(dt)
                    if roach.escaped():
                        roaches.remove(roach)
                        lives -= 1

                # A hit requires both fast movement and a trajectory crossing.
                # At most one roach is removed for this scoring opportunity.
                if (
                    valid_sample
                    and swing_armed
                    and pointer_speed >= MIN_SWING_SPEED
                    and now - last_hit_time >= HIT_COOLDOWN
                ):
                    for roach in roaches:
                        distance = point_to_segment_distance(
                            (roach.x, roach.y),
                            previous_pointer,
                            pointer,
                        )

                        if distance <= ROACH_RADIUS + POINTER_RADIUS:
                            points = 30 if roach.golden else 10
                            score += points
                            eliminated += 1

                            feedback_text = f"+{points} SMASH!"
                            feedback_position = (
                                max(20, min(WIDTH - 245, int(roach.x))),
                                max(
                                    PLAY_TOP,
                                    min(PLAY_BOTTOM - 50, int(roach.y)),
                                ),
                            )
                            feedback_until = now + 0.55

                            splats.append(
                                Splat(
                                    int(roach.x),
                                    int(roach.y),
                                    roach.golden,
                                    now,
                                )
                            )

                            roaches.remove(roach)
                            last_hit_time = now
                            swing_armed = False
                            break

                if time_left <= 0 or lives <= 0:
                    state = "game_over"
                    if score > high_score:
                        high_score = score
                        save_high_score(high_score)

            previous_pointer = pointer
            previous_sample_time = now

            screen.fill(BACKGROUND)

            if state == "start":
                draw_centered(
                    screen, title_font, "ROACH SMASH!", 85, YELLOW
                )
                draw_centered(
                    screen,
                    text_font,
                    "Sweep quickly across roaches to smash them.",
                    195,
                )
                draw_centered(
                    screen,
                    text_font,
                    "Hovering does not count. Escapes cost a life!",
                    235,
                )
                draw_centered(
                    screen,
                    small_font,
                    f"High score: {high_score}",
                    285,
                )

                pygame.draw.rect(
                    screen, BUTTON, button_rect, border_radius=15
                )
                draw_centered(
                    screen, heading_font, "PLAY", button_rect.y + 12
                )
                draw_centered(
                    screen,
                    small_font,
                    "Tap PLAY or press Enter/Space",
                    440,
                )

            elif state == "playing":
                pygame.draw.rect(
                    screen,
                    PLAY_AREA,
                    (0, PLAY_TOP, WIDTH, PLAY_BOTTOM - PLAY_TOP),
                )
                pygame.draw.line(
                    screen,
                    (96, 83, 113),
                    (0, PLAY_TOP),
                    (WIDTH, PLAY_TOP),
                    3,
                )

                score_image = heading_font.render(
                    f"Score {score}", True, YELLOW
                )
                timer_image = heading_font.render(
                    f"{math.ceil(time_left)}s", True, WHITE
                )
                lives_image = heading_font.render(
                    f"Lives {lives}", True, RED
                )

                screen.blit(score_image, (25, 25))
                screen.blit(
                    timer_image,
                    ((WIDTH - timer_image.get_width()) // 2, 25),
                )
                screen.blit(
                    lives_image,
                    (WIDTH - lives_image.get_width() - 25, 25),
                )

                for roach in roaches:
                    draw_roach(screen, roach)

                splats[:] = [
                    splat
                    for splat in splats
                    if now - splat.started_at < SPLAT_DURATION
                ]
                for splat in splats:
                    draw_splat(screen, splat, now)

                if now < feedback_until:
                    image = heading_font.render(
                        feedback_text, True, YELLOW
                    )
                    screen.blit(image, feedback_position)

                pygame.draw.circle(
                    screen, GREEN, pointer, POINTER_RADIUS, 3
                )

                status = "READY" if swing_armed else "SLOW DOWN"
                speed_image = small_font.render(
                    f"Speed {pointer_speed:.0f} px/s | {status}",
                    True,
                    WHITE,
                )
                screen.blit(speed_image, (20, HEIGHT - 38))

            else:  # game_over
                draw_centered(
                    screen, title_font, "GAME OVER!", 65, YELLOW
                )
                draw_centered(
                    screen, heading_font, f"Final score: {score}", 170
                )
                draw_centered(
                    screen,
                    text_font,
                    f"Roaches eliminated: {eliminated}",
                    230,
                )
                draw_centered(
                    screen,
                    text_font,
                    f"High score: {high_score}",
                    270,
                )

                pygame.draw.rect(
                    screen, BUTTON, button_rect, border_radius=15
                )
                draw_centered(
                    screen,
                    text_font,
                    "PLAY AGAIN",
                    button_rect.y + 20,
                )
                draw_centered(
                    screen,
                    small_font,
                    "Tap PLAY AGAIN or press Enter/Space",
                    440,
                )

            pygame.display.flip()

    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
