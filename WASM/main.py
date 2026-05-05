#!/usr/bin/env python3
"""
Galamax - A Galaxian-style arcade game built with Pygame
Web / WASM version (pygbag-compatible async entry point)

Controls:
  Arrow Keys / A D  - Move ship
  Space             - Fire
  Escape            - Return to menu
    Touch (mobile)    - On-screen Left / Right / Fire buttons
"""

import asyncio
import pygame
import sys
import random
import math
import array
import os

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

SCREEN_W, SCREEN_H = 800, 600
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("GALAMAX")
clock = pygame.time.Clock()
FPS = 60

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BLACK   = (  0,   0,   0)
WHITE   = (255, 255, 255)
RED     = (255,  60,  60)
GREEN   = ( 60, 220,  60)
YELLOW  = (255, 220,   0)
CYAN    = (  0, 200, 255)
MAGENTA = (220,   0, 255)
ORANGE  = (255, 140,   0)
GOLD    = (255, 200,   0)
PURPLE  = (180,   0, 220)
LIME    = (180, 255,   0)
PINK    = (255, 100, 200)
DIM_BLUE= ( 40,  40,  80)

# ---------------------------------------------------------------------------
# Game-state constants
# ---------------------------------------------------------------------------
MENU        = 0
PLAYING     = 1
GAME_OVER   = 2
LEVEL_CLEAR = 3
WIN         = 4

# ---------------------------------------------------------------------------
# Enemy type constants & scoring
# ---------------------------------------------------------------------------
BEE       = 0
BUTTERFLY = 1
BOSS      = 2

BASE_PTS  = {BEE: 50, BUTTERFLY: 80, BOSS: 150}
DIVE_MULT = 2   # score multiplier when hitting a diving enemy

# ---------------------------------------------------------------------------
# Utility draw functions  (no image files required)
# ---------------------------------------------------------------------------

def draw_ship(surf, cx, cy, size=20):
    """Player ship – green arrowhead with cyan engine glow."""
    pts = [
        (cx,               cy - size),
        (cx - size * 0.7,  cy + size * 0.6),
        (cx,               cy + size * 0.15),
        (cx + size * 0.7,  cy + size * 0.6),
    ]
    pygame.draw.polygon(surf, GREEN, pts)
    pygame.draw.polygon(surf, CYAN, [
        (cx - size * 0.25, cy + size * 0.1),
        (cx,               cy + size * 0.72),
        (cx + size * 0.25, cy + size * 0.1),
    ])
    pygame.draw.circle(surf, CYAN, (cx, int(cy - size * 0.25)), max(2, size // 5))


def draw_bee(surf, cx, cy, size=14, alt=False):
    col = GOLD if alt else YELLOW
    pygame.draw.ellipse(surf, CYAN,
        (cx - size,      cy - size // 2, size * 3 // 4, size // 2))
    pygame.draw.ellipse(surf, CYAN,
        (cx + size // 4, cy - size // 2, size * 3 // 4, size // 2))
    pygame.draw.ellipse(surf, col,
        (cx - size // 2, cy - size // 3, size, size * 2 // 3))
    pygame.draw.circle(surf, RED, (cx - size // 4, cy - size // 8), 2)
    pygame.draw.circle(surf, RED, (cx + size // 4, cy - size // 8), 2)


def draw_butterfly(surf, cx, cy, size=16, alt=False):
    col1 = PINK if alt else MAGENTA
    col2 = PURPLE
    pygame.draw.ellipse(surf, col1, (cx - size, cy - size // 2, size, size))
    pygame.draw.ellipse(surf, col1, (cx,        cy - size // 2, size, size))
    pygame.draw.ellipse(surf, col2,
        (cx - size * 3 // 4, cy, size * 3 // 4, size * 2 // 3))
    pygame.draw.ellipse(surf, col2,
        (cx,                 cy, size * 3 // 4, size * 2 // 3))
    pygame.draw.ellipse(surf, WHITE, (cx - 3, cy - size // 2, 6, size))


def draw_boss(surf, cx, cy, size=18, alt=False):
    col  = ORANGE if alt else RED
    col2 = RED    if alt else ORANGE
    body = [
        (cx,              cy - size),
        (cx + size * 0.8, cy - size * 0.2),
        (cx + size * 0.5, cy + size * 0.8),
        (cx - size * 0.5, cy + size * 0.8),
        (cx - size * 0.8, cy - size * 0.2),
    ]
    pygame.draw.polygon(surf, col, body)
    pygame.draw.polygon(surf, col2, [
        (cx,              cy - size * 0.5),
        (cx + size * 0.6, cy - size * 0.1),
        (cx,              cy + size * 0.3),
    ])
    pygame.draw.polygon(surf, col2, [
        (cx,              cy - size * 0.5),
        (cx - size * 0.6, cy - size * 0.1),
        (cx,              cy + size * 0.3),
    ])
    pygame.draw.circle(surf, GOLD,  (cx, cy), size // 3)
    pygame.draw.circle(surf, WHITE, (cx, cy), size // 5)


# ---------------------------------------------------------------------------
# Sound manager  (all sounds synthesised – no audio files required)
# ---------------------------------------------------------------------------

class SoundManager:
    _RATE = 44100

    def __init__(self):
        try:
            if not pygame.mixer.get_init():
                self._ok = False
                return
            self._ok = True
            self.shoot        = self._make_laser()
            self.enemy_shoot  = self._make_enemy_laser()
            self.explode      = self._make_explode(big=False)
            self.explode_big  = self._make_explode(big=True)
            self.player_die   = self._make_player_die()
            self.level_clear  = self._make_level_clear()
            self.oh_yeah      = self._load_audio_file("OhYeah")
            self.intro        = self._load_audio_file("spcokIntro") or self._load_audio_file("spockIntro")
            self.middle_track = (
                self._load_audio_file("spockMiddle")
                or self._load_audio_file("spcokMiddle")
                or self._make_middle_track()
            )

            # Keep wave music loud while reducing all other SFX by 50%.
            self.shoot.set_volume(0.5)
            self.enemy_shoot.set_volume(0.5)
            self.explode.set_volume(0.72)
            self.explode_big.set_volume(0.78)
            self.player_die.set_volume(0.5)
            self.level_clear.set_volume(0.5)
            if self.oh_yeah:
                self.oh_yeah.set_volume(0.9)
            if self.intro:
                self.intro.set_volume(0.9)

            # Pre-load all wave beat tracks so they are ready at wave start
            # (avoids WASM virtual-FS timing failures on first wave).
            self._wave_beat_cache = {}
            for _i in range(1, 7):
                _snd = self._load_audio_file(f"spockBeat{_i}")
                if _snd:
                    self._wave_beat_cache[_i] = _snd

            self._beat_ch     = pygame.mixer.Channel(0)
            self._beat_sounds = self._make_beat_pair()
            for snd in self._beat_sounds:
                snd.set_volume(snd.get_volume() * 0.5)
            self._beat_idx    = 0
            self._beat_timer  = 0
            self._beat_interval = 40
            self._wave_ch     = pygame.mixer.Channel(1)
            self._intro_ch    = pygame.mixer.Channel(2)
            self._event_ch    = pygame.mixer.Channel(3)
            self._wave_mode   = False
            self._wave_start_count = 0
        except Exception:
            self._ok = False

    @classmethod
    def _buf(cls, samples):
        raw = array.array('h', (max(-32767, min(32767, int(s * 32767)))
                                for s in samples))
        return pygame.mixer.Sound(buffer=raw)

    @classmethod
    def _sine(cls, freq, dur, amp=1.0, attack=0.01, decay=0.1):
        n = int(cls._RATE * dur)
        atk = int(cls._RATE * attack)
        dcy = int(cls._RATE * decay)
        out = []
        for i in range(n):
            env = 1.0
            if i < atk:
                env = i / atk
            elif i > n - dcy:
                env = (n - i) / dcy
            out.append(amp * env * math.sin(2 * math.pi * freq * i / cls._RATE))
        return out

    @classmethod
    def _sweep(cls, f0, f1, dur, amp=1.0):
        n = int(cls._RATE * dur)
        out = []
        phase = 0.0
        for i in range(n):
            t     = i / n
            freq  = f0 + (f1 - f0) * t
            env   = 1.0 - t
            out.append(amp * env * math.sin(phase))
            phase += 2 * math.pi * freq / cls._RATE
        return out

    @classmethod
    def _noise(cls, dur, amp=1.0):
        n = int(cls._RATE * dur)
        return [amp * (random.random() * 2 - 1) * (1 - i / n) for i in range(n)]

    @classmethod
    def _mix(cls, *layers):
        length = max(len(l) for l in layers)
        out = [0.0] * length
        for layer in layers:
            for i, v in enumerate(layer):
                out[i] += v
        peak = max(abs(v) for v in out) or 1.0
        return [v / peak for v in out]

    def _make_laser(self):
        core = self._sweep(1450, 320, 0.11, 0.95)
        harmonic = self._sweep(2100, 520, 0.10, 0.38)
        click = self._sine(2600, 0.018, 0.35, attack=0.002, decay=0.014)
        air = self._noise(0.06, 0.08)
        return self._buf(self._mix(core, harmonic, click, air))

    def _make_enemy_laser(self):
        growl = self._sweep(560, 130, 0.16, 0.75)
        undertone = self._sweep(300, 90, 0.17, 0.5)
        bite = self._sine(980, 0.04, 0.22, attack=0.003, decay=0.03)
        grit = self._noise(0.16, 0.16)
        return self._buf(self._mix(growl, undertone, bite, grit))

    def _make_explode(self, big=False):
        if big:
            dur = 0.48
            noise = self._noise(dur, 0.95)
            low_sweep = self._sweep(82, 24, dur, 0.72)
            sub_thump = self._sine(48, 0.20, 0.82, attack=0.002, decay=0.18)
            body = self._sine(62, 0.22, 0.45, attack=0.003, decay=0.16)
            return self._buf(self._mix(noise, low_sweep, sub_thump, body))

        dur = 0.26
        noise = self._noise(dur, 0.78)
        low_sweep = self._sweep(120, 36, dur, 0.58)
        sub_thump = self._sine(66, 0.12, 0.56, attack=0.002, decay=0.10)
        body = self._sine(86, 0.14, 0.32, attack=0.003, decay=0.10)
        return self._buf(self._mix(noise, low_sweep, sub_thump, body))

    def _make_player_die(self):
        return self._buf(self._mix(self._sweep(600, 80, 0.5, 0.8),
                                   self._noise(0.5, 0.4)))

    def _make_level_clear(self):
        # Spectacular fanfare: lead melody + harmony + bass pulse.
        melody = [523, 659, 784, 880, 1047, 988, 1175]
        harmony = [392, 494, 587, 659, 784, 740, 880]
        bass = [131, 147, 165, 196, 220, 196, 262]

        samples = []
        for i in range(len(melody)):
            dur = 0.11 if i < len(melody) - 1 else 0.24
            lead = self._sine(melody[i], dur, 0.95, attack=0.008, decay=0.08)
            harm = self._sine(harmony[i], dur, 0.45, attack=0.008, decay=0.09)
            low = self._sine(bass[i], dur, 0.32, attack=0.004, decay=0.10)
            sparkle = self._sine(melody[i] * 2, dur, 0.18, attack=0.003, decay=0.06)
            samples += self._mix(lead, harm, low, sparkle)

        return self._buf(samples)

    def _make_middle_track(self):
        # Procedural fallback so "middle" can still be heard if file is missing.
        phrase = [330, 392, 440, 392, 349, 294]
        samples = []
        for freq in phrase:
            lead = self._sine(freq, 0.14, 0.65, attack=0.01, decay=0.08)
            pad = self._sine(freq * 0.5, 0.14, 0.35, attack=0.01, decay=0.10)
            samples += self._mix(lead, pad)
        return self._buf(samples)

    def _make_beat_pair(self):
        hi = self._buf(self._sine(880, 0.04, 0.5, attack=0.005, decay=0.035))
        lo = self._buf(self._sine(440, 0.05, 0.5, attack=0.005, decay=0.04))
        hi.set_volume(0.18)
        lo.set_volume(0.18)
        return [hi, lo]

    def _load_audio_file(self, base_name, assets_dir="assets/audio"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for ext in (".wav", ".ogg"):
            file_name = f"{base_name}{ext}"
            for path in (os.path.join(base_dir, assets_dir, file_name), os.path.join(assets_dir, file_name)):
                if not os.path.exists(path):
                    continue
                try:
                    return pygame.mixer.Sound(path)
                except Exception:
                    continue
        return None

    def play(self, sound):
        if self._ok:
            try:
                sound.play()
            except Exception:
                pass

    def play_oh_yeah(self):
        if not self._ok or not self.oh_yeah:
            return False
        # Dedicated channel avoids the sound being dropped when many SFX fire together.
        try:
            self._event_ch.stop()
            self._event_ch.play(self.oh_yeah)
            return True
        except Exception:
            return False

    def start_wave_beat(self, level, assets_dir="assets/audio"):
        """Play wave music, occasionally using spockMiddle instead of spockBeat{level}."""
        if not self._ok:
            return False

        self._wave_mode = False
        self._wave_start_count += 1
        # Deterministic cadence: play middle track less frequently.
        play_middle = (self._wave_start_count % 5 == 0)
        middle_names = ["spockMiddle", "spcokMiddle"]
        middle_first = middle_names + [f"spockBeat{level}"]
        beat_first = [f"spockBeat{level}"] + middle_names
        order = middle_first if play_middle else beat_first

        beat_idx = ((level - 1) % 6) + 1  # clamp to 1-6
        for name in order:
            if name in middle_names:
                beat = self.middle_track
            else:
                # Use pre-loaded cache; fall back to on-demand load if missing.
                beat = self._wave_beat_cache.get(beat_idx) or self._load_audio_file(name, assets_dir=assets_dir)
            if beat is None:
                continue
            beat.set_volume(0.70)
            self._wave_ch.play(beat, loops=-1)
            self._wave_mode = True
            return True
        return False

    def update_beat(self, enemy_count, total_enemies):
        if not self._ok or enemy_count == 0 or self._wave_mode:
            return
        ratio = enemy_count / max(total_enemies, 1)
        self._beat_interval = max(10, int(40 * ratio))
        self._beat_timer += 1
        if self._beat_timer >= self._beat_interval:
            self._beat_timer = 0
            snd = self._beat_sounds[self._beat_idx % 2]
            try:
                self._beat_ch.play(snd)
            except Exception:
                pass
            self._beat_idx += 1

    def stop_beat(self):
        if self._ok:
            try:
                self._beat_ch.stop()
                self._wave_ch.stop()
                self._wave_mode = False
            except Exception:
                pass

    def start_intro_music(self):
        if not self._ok or not self.intro:
            return
        try:
            if not self._intro_ch.get_busy():
                self._intro_ch.play(self.intro, loops=-1)
        except Exception:
            pass

    def stop_intro_music(self):
        if self._ok:
            try:
                self._intro_ch.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Background stars
# ---------------------------------------------------------------------------

class Star:
    def __init__(self, y=None):
        self._init(y if y is not None else random.randint(0, SCREEN_H))

    def _init(self, y=0):
        self.x      = random.randint(0, SCREEN_W)
        self.y      = float(y)
        self.speed  = random.uniform(0.25, 1.2)
        self.bright = random.randint(35, 105)
        self.size   = 1

    def update(self):
        self.y += self.speed
        if self.y > SCREEN_H:
            self._init()

    def draw(self, surf):
        b = self.bright
        pygame.draw.circle(surf, (b // 3, b // 2, b), (int(self.x), int(self.y)), self.size)


# ---------------------------------------------------------------------------
# Particle & Explosion
# ---------------------------------------------------------------------------

class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size')

    def __init__(self, x, y, vx, vy, life, color, size):
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size  = size

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.08
        self.vx *= 0.98
        self.life -= 1

    def draw(self, surf):
        if self.life <= 0:
            return
        alpha = self.life / self.max_life
        r, g, b = self.color
        pygame.draw.circle(
            surf,
            (int(r * alpha), int(g * alpha), int(b * alpha)),
            (int(self.x), int(self.y)),
            max(1, self.size),
        )


class Explosion:
    def __init__(self, x, y, color=ORANGE, big=False):
        count = 22 if big else 14
        alt   = YELLOW if color != YELLOW else WHITE
        self.particles = []
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.0, 5.0 if big else 3.0)
            self.particles.append(Particle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                random.randint(20, 40),
                color if random.random() > 0.35 else alt,
                random.randint(2, 5 if big else 3),
            ))

    @property
    def done(self):
        return all(p.life <= 0 for p in self.particles)

    def update(self):
        for p in self.particles:
            p.update()

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)


# ---------------------------------------------------------------------------
# Bullet
# ---------------------------------------------------------------------------

class Bullet:
    def __init__(self, x, y, vy, is_enemy=False, vx=0.0):
        self.x, self.y = float(x), float(y)
        self.vx       = float(vx)
        self.vy       = vy
        self.is_enemy = is_enemy
        self.alive    = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -30 or self.y > SCREEN_H + 30 or self.x < -40 or self.x > SCREEN_W + 40:
            self.alive = False

    def rect(self):
        return pygame.Rect(int(self.x) - 2, int(self.y) - 8, 4, 16)

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.is_enemy:
            pygame.draw.rect(surf, ORANGE, (x - 2, y - 6,  4, 12))
            pygame.draw.rect(surf, WHITE,  (x - 1, y - 4,  2,  8))
        else:
            pygame.draw.rect(surf, LIME,   (x - 2, y - 10, 4, 20))
            pygame.draw.rect(surf, WHITE,  (x - 1, y -  8, 2, 16))


# ---------------------------------------------------------------------------
# Enemy
# ---------------------------------------------------------------------------

class Enemy:
    COLS        = 10
    ROWS        = 5
    SPACING_X   = 60
    SPACING_Y   = 50
    LEFT_MARGIN = 85
    TOP_MARGIN  = 90

    def __init__(self, col, row, etype):
        self.col, self.row = col, row
        self.etype   = etype
        self.home_x  = self.LEFT_MARGIN + col * self.SPACING_X
        self.home_y  = self.TOP_MARGIN  + row * self.SPACING_Y
        self.x       = float(self.home_x)
        self.y       = float(self.home_y)
        self.alive     = True
        self.diving    = False
        self.returning = False
        self._path     = []
        self._path_idx = 0
        self.dive_speed= 3.0
        self._anim_t   = random.randint(0, 15)
        self._alt      = False

    @property
    def size(self):
        return (14, 16, 18)[self.etype]

    def points(self):
        return BASE_PTS[self.etype] * (DIVE_MULT if self.diving else 1)

    def hitbox(self):
        s = self.size
        return pygame.Rect(int(self.x) - s, int(self.y) - s, s * 2, s * 2)

    def start_dive(self, target_x, level):
        if self.diving or self.returning:
            return
        self.diving    = True
        sx, sy         = self.x, self.y
        mx1 = sx + random.uniform(-200, 200)
        my1 = sy + random.uniform(60, 160)
        mx2 = target_x + random.uniform(-120, 120)
        my2 = SCREEN_H * 0.5
        ex  = target_x + random.uniform(-30, 30)
        ey  = SCREEN_H + 50
        self._path     = self._bezier((sx, sy), (mx1, my1), (mx2, my2), (ex, ey), 130)
        self._path_idx = 0
        self.dive_speed= 3.0 + level * 0.25

    @staticmethod
    def _bezier(p0, p1, p2, p3, n):
        pts = []
        for i in range(n):
            t  = i / n
            mt = 1.0 - t
            x  = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
            y  = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
            pts.append((x, y))
        return pts

    def update(self, fdx, level):
        self._anim_t += 1
        if self._anim_t >= 10:
            self._anim_t = 0
            self._alt    = not self._alt

        if self.diving:
            if self._path_idx >= len(self._path):
                self.diving    = False
                self.returning = True
                self.x         = float(self.home_x)
                self.y         = -50.0
            else:
                tx, ty = self._path[self._path_idx]
                dx, dy = tx - self.x, ty - self.y
                d = math.hypot(dx, dy)
                if d < self.dive_speed + 1:
                    self._path_idx += 1
                else:
                    self.x += dx / d * self.dive_speed
                    self.y += dy / d * self.dive_speed

        elif self.returning:
            target_x = self.home_x + fdx
            self.x  += (target_x - self.x) * 0.12
            if self.y < self.home_y:
                self.y += 2.8
            else:
                self.y         = float(self.home_y)
                self.returning = False

        else:
            self.x = self.home_x + fdx
            self.y = float(self.home_y)

    def draw(self, surf, wave_sprite=None):
        cx, cy = int(self.x), int(self.y)
        if wave_sprite is not None:
            sprite = wave_sprite.get(self.size)
            if sprite is not None:
                surf.blit(sprite, (cx - sprite.get_width() // 2, cy - sprite.get_height() // 2))
                return
        a = self._alt
        if   self.etype == BEE:       draw_bee(surf, cx, cy, self.size, a)
        elif self.etype == BUTTERFLY: draw_butterfly(surf, cx, cy, self.size, a)
        else:                         draw_boss(surf, cx, cy, self.size, a)


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player:
    SPEED = 5
    _sprite_cache = {}

    def __init__(self):
        self.x          = float(SCREEN_W // 2)
        self.y          = float(SCREEN_H - 55)
        self.lives      = 3
        self.invincible = 0
        self._shoot_cd  = 0
        self.size       = 20
        self._sprite = self._get_sprite(self.size)

    @classmethod
    def _cleanup_sprite(cls, src_surf):
        out = src_surf.copy().convert_alpha()
        w, h = out.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = out.get_at((x, y))
                spread = max(r, g, b) - min(r, g, b)
                luma = (r + g + b) // 3
                if r >= 236 and g >= 236 and b >= 236:
                    out.set_at((x, y), (r, g, b, 0))
                elif spread <= 20 and luma >= 200:
                    out.set_at((x, y), (r, g, b, min(a, 56)))
        return out

    @classmethod
    def _get_sprite(cls, size):
        if size in cls._sprite_cache:
            return cls._sprite_cache[size]
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "assets", "sprites", "player.jpeg"),
            os.path.join("assets", "sprites", "player.jpeg"),
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            cls._sprite_cache[size] = None
            return None
        try:
            raw = pygame.image.load(path).convert_alpha()
            target = max(20, int(size * 2.0))
            scaled = pygame.transform.smoothscale(raw, (target, target))
            cls._sprite_cache[size] = cls._cleanup_sprite(scaled)
        except Exception:
            cls._sprite_cache[size] = None
        return cls._sprite_cache[size]

    def update(self, keys, touch=None):
        touch = touch or {}
        move_left = keys[pygame.K_LEFT] or keys[pygame.K_a] or touch.get("left", False)
        move_right = keys[pygame.K_RIGHT] or keys[pygame.K_d] or touch.get("right", False)
        move_up = keys[pygame.K_UP] or keys[pygame.K_w] or touch.get("up", False)
        move_down = keys[pygame.K_DOWN] or keys[pygame.K_s] or touch.get("down", False)

        if move_left: self.x -= self.SPEED
        if move_right: self.x += self.SPEED
        if move_up: self.y -= self.SPEED
        if move_down: self.y += self.SPEED
        self.x = max(self.size, min(SCREEN_W - self.size, self.x))
        self.y = max(150, min(SCREEN_H - 50, self.y))
        if self.invincible > 0: self.invincible -= 1
        if self._shoot_cd  > 0: self._shoot_cd  -= 1

    def shoot(self):
        if self._shoot_cd > 0:
            return None
        self._shoot_cd = 8
        return Bullet(self.x, self.y - self.size, vy=-13)

    def hitbox(self):
        s = self.size // 2
        return pygame.Rect(
            int(self.x) - s, int(self.y) - self.size + 4, s * 2, self.size - 4
        )

    def draw(self, surf):
        if self.invincible > 0 and (self.invincible // 4) % 2:
            return
        if self._sprite is not None:
            surf.blit(
                self._sprite,
                (int(self.x) - self._sprite.get_width() // 2, int(self.y) - self._sprite.get_height() // 2),
            )
            return
        draw_ship(surf, int(self.x), int(self.y), self.size)


class Mothership:
    def __init__(self, level, sprite=None):
        self.level = level
        self.sprite = sprite
        self.w = 132
        self.h = 68
        self.x = float(SCREEN_W // 2)
        self.y = float(-self.h)
        self.speed_x = 2.0 + level * 0.15
        self.speed_y = 2.2 + level * 0.08
        self.dir = random.choice([-1, 1])
        self.hp = 10
        self.alive = True
        self.shoot_cd = 0
        self.shoot_interval = max(18, 58 - level * 3)

    def update(self):
        if self.y < 90:
            self.y += self.speed_y
            return
        self.x += self.dir * self.speed_x
        if self.x <= 70:
            self.x = 70
            self.dir = 1
        elif self.x >= SCREEN_W - 70:
            self.x = SCREEN_W - 70
            self.dir = -1

    def hitbox(self):
        return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h // 2), self.w, self.h)

    def take_hit(self):
        self.hp -= 1
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def spray_lasers(self):
        base_y = self.y + self.h * 0.42
        speed = 4.8 + self.level * 0.35
        spread = 2.2 + self.level * 0.08
        return [
            Bullet(self.x - 16, base_y, vy=speed, is_enemy=True, vx=-spread),
            Bullet(self.x,      base_y, vy=speed + 0.2, is_enemy=True, vx=0.0),
            Bullet(self.x + 16, base_y, vy=speed, is_enemy=True, vx=spread),
        ]

    def draw(self, surf):
        if self.sprite is not None:
            surf.blit(self.sprite, (int(self.x - self.sprite.get_width() // 2), int(self.y - self.sprite.get_height() // 2)))
            return
        body = self.hitbox()
        pygame.draw.rect(surf, (120, 40, 220), body, border_radius=14)
        pygame.draw.rect(surf, CYAN, body.inflate(-16, -22), 2, border_radius=10)
        pygame.draw.circle(surf, RED, (int(self.x), int(self.y + 8)), 8)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    MAX_ENEMY_BULLETS = 8

    def __init__(self):
        self.high_score = 0
        self._init_fonts()
        self.stars = [Star(random.randint(0, SCREEN_H)) for _ in range(75)]
        self.sfx   = SoundManager()
        self._total_enemies = Enemy.ROWS * Enemy.COLS
        self._start_screen = self._load_start_screen()
        self._shake_frames = 0
        self._shake_power  = 0
        self._flash_alpha  = 0
        self._flash_decay  = 0
        self._restart_lock_until = 0
        self._touch_contacts = {}
        self._touch_state = {"left": False, "right": False, "up": False, "down": False, "fire": False}
        self._touch_seen = False
        self._show_touch_controls = (sys.platform == "emscripten")
        self.state = MENU
        self._reset()
        self.sfx.stop_beat()

    def _init_fonts(self):
        self.f_big = pygame.font.SysFont('monospace', 52, bold=True)
        self.f_med = pygame.font.SysFont('monospace', 30, bold=True)
        self.f_sm  = pygame.font.SysFont('monospace', 18)

    def _load_start_screen(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "assets", "backgrounds", "start_screen.png"),
            os.path.join("assets", "backgrounds", "start_screen.png"),
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            return None
        try:
            raw = pygame.image.load(path).convert()
            return pygame.transform.scale(raw, (SCREEN_W, SCREEN_H))
        except Exception:
            return None

    def _make_white_transparent(self, src_surf, cutoff=238):
        out = src_surf.copy().convert_alpha()
        w, h = out.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = out.get_at((x, y))
                if r >= cutoff and g >= cutoff and b >= cutoff:
                    out.set_at((x, y), (r, g, b, 0))
                else:
                    out.set_at((x, y), (r, g, b, a))
        return out

    def _cleanup_enemy_sprite(self, src_surf):
        out = self._make_white_transparent(src_surf)
        w, h = out.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = out.get_at((x, y))
                if a == 0:
                    continue
                spread = max(r, g, b) - min(r, g, b)
                luma = (r + g + b) // 3
                # Remove bright neutral matte pixels and soften halo fringe.
                if spread <= 16 and luma >= 205:
                    out.set_at((x, y), (r, g, b, 0))
                elif spread <= 20 and luma >= 182:
                    out.set_at((x, y), (r, g, b, min(a, 64)))
        return out

    def _reset(self):
        self.score = 0
        self.level = 1
        self._init_level(keep_lives=False)

    def _init_level(self, keep_lives=True):
        carried_lives = 3
        if keep_lives and hasattr(self, "player") and self.player is not None:
            carried_lives = self.player.lives
        self.player        = Player()
        self.player.lives  = carried_lives
        self.p_bullets     = []
        self.e_bullets     = []
        self.explosions    = []
        self.enemies       = self._make_enemies()
        self._total_enemies = len(self.enemies)
        self.fdx           = 0.0
        self.fdir          = 1
        self.fspeed        = 0.4 + self.level * 0.12
        self.shoot_timer   = 0
        self.shoot_interval= max(6, 72 - self.level * 8)
        self.clear_timer   = 0
        self.sfx.start_wave_beat(self.level)
        self._mothership = None
        self._mship_spawned = False
        self._mship_sprite = None
        self._flash_alpha = 0
        self._flash_decay = 0
        base_dir = os.path.dirname(os.path.abspath(__file__))
        bg_path = next(
            (p for p in [
                os.path.join(base_dir, "assets", "backgrounds", f"galaxy{self.level}.jpg"),
                os.path.join("assets", "backgrounds", f"galaxy{self.level}.jpg"),
            ] if os.path.exists(p)),
            None
        )
        try:
            raw = pygame.image.load(bg_path).convert()
            self._bg_surf = pygame.transform.scale(raw, (SCREEN_W, SCREEN_H))
        except Exception:
            self._bg_surf = None
        self._enemy_sprite = None
        self._enemy_sprite_by_size = None
        enemy_path = next(
            (
                p
                for ext in (".jpeg", ".jpg", ".png")
                for p in [
                    os.path.join(base_dir, "assets", "sprites", f"enemy{self.level}{ext}"),
                    os.path.join("assets", "sprites", f"enemy{self.level}{ext}"),
                ]
                if os.path.exists(p)
            ),
            None,
        )
        if enemy_path:
            try:
                self._enemy_sprite = pygame.image.load(enemy_path).convert_alpha()
                self._enemy_sprite_by_size = {
                    14: self._cleanup_enemy_sprite(pygame.transform.smoothscale(self._enemy_sprite, (28, 28))),
                    16: self._cleanup_enemy_sprite(pygame.transform.smoothscale(self._enemy_sprite, (32, 32))),
                    18: self._cleanup_enemy_sprite(pygame.transform.smoothscale(self._enemy_sprite, (36, 36))),
                }
            except Exception:
                self._enemy_sprite = None
                self._enemy_sprite_by_size = None
        mothership_path = next(
            (
                p
                for ext in (".png", ".jpeg", ".jpg")
                for p in [
                    os.path.join(base_dir, "assets", "sprites", f"mothership{self.level}{ext}"),
                    os.path.join("assets", "sprites", f"mothership{self.level}{ext}"),
                ]
                if os.path.exists(p)
            ),
            None,
        )
        if mothership_path:
            try:
                raw_ship = pygame.image.load(mothership_path).convert_alpha()
                scaled_ship = pygame.transform.smoothscale(raw_ship, (132, 68))
                self._mship_sprite = self._cleanup_enemy_sprite(scaled_ship)
            except Exception:
                self._mship_sprite = None

    def _make_enemies(self):
        row_types = [BEE, BEE, BUTTERFLY, BUTTERFLY, BOSS]
        active_cols = range(2, 8)
        return [
            Enemy(col, row, row_types[row])
            for row in range(Enemy.ROWS)
            for col in active_cols
        ]

    def _alive(self):
        return [e for e in self.enemies if e.alive]

    def _alive_static(self):
        return [e for e in self._alive() if not e.diving and not e.returning]

    def _wave_from_key(self, key):
        key_to_wave = {
            pygame.K_1: 1,
            pygame.K_2: 2,
            pygame.K_3: 3,
            pygame.K_4: 4,
            pygame.K_5: 5,
            pygame.K_6: 6,
            pygame.K_7: 7,
            pygame.K_8: 8,
            pygame.K_9: 9,
            pygame.K_0: 10,
        }
        return key_to_wave.get(key)

    def _trigger_shake(self, power=5, frames=7):
        self._shake_power = max(self._shake_power, power)
        self._shake_frames = max(self._shake_frames, frames)

    def _apply_screen_shake(self):
        if self._shake_frames <= 0:
            return
        dx = random.randint(-self._shake_power, self._shake_power)
        dy = random.randint(-self._shake_power, self._shake_power)
        frame = screen.copy()
        screen.fill(BLACK)
        screen.blit(frame, (dx, dy))
        self._shake_frames -= 1
        if self._shake_frames <= 0:
            self._shake_power = 0

    def _trigger_flash(self, alpha=220, decay=52):
        self._flash_alpha = max(self._flash_alpha, alpha)
        self._flash_decay = max(self._flash_decay, decay)

    def _draw_flash(self):
        if self._flash_alpha <= 0:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((255, 245, 220, min(255, int(self._flash_alpha))))
        screen.blit(overlay, (0, 0))
        self._flash_alpha = max(0, self._flash_alpha - self._flash_decay)

    def _restart_delay_remaining_ms(self):
        return max(0, self._restart_lock_until - pygame.time.get_ticks())

    def _max_enemy_bullets_for_wave(self):
        return min(18, self.MAX_ENEMY_BULLETS + (self.level - 1))

    def _touch_buttons(self):
        # Big targets improve mobile control reliability.
        left = pygame.Rect(26, SCREEN_H - 124, 84, 84)
        right = pygame.Rect(124, SCREEN_H - 124, 84, 84)
        fire = pygame.Rect(SCREEN_W - 134, SCREEN_H - 134, 108, 108)
        return left, right, fire

    def _actions_for_touch_point(self, x, y):
        actions = set()
        left, right, fire = self._touch_buttons()
        if left.collidepoint(x, y):
            actions.add("left")
        if right.collidepoint(x, y):
            actions.add("right")
        if fire.collidepoint(x, y):
            actions.add("fire")
        return actions

    def _rebuild_touch_state(self):
        self._touch_state = {"left": False, "right": False, "up": False, "down": False, "fire": False}
        for actions in self._touch_contacts.values():
            for action in actions:
                self._touch_state[action] = True

    def _clear_touch_state(self):
        self._touch_contacts.clear()
        self._rebuild_touch_state()

    def _handle_touch_event(self, event):
        self._touch_seen = True
        self._show_touch_controls = True

        if event.type == pygame.FINGERUP:
            self._touch_contacts.pop(event.finger_id, None)
            self._rebuild_touch_state()
            return

        x = int(event.x * SCREEN_W)
        y = int(event.y * SCREEN_H)
        actions = self._actions_for_touch_point(x, y)
        if actions:
            self._touch_contacts[event.finger_id] = actions
        else:
            self._touch_contacts.pop(event.finger_id, None)
        self._rebuild_touch_state()

    def _maybe_spawn_mothership(self):
        if self._mship_spawned:
            return
        threshold = max(3, int(self._total_enemies * 0.35))
        if len(self._alive()) <= threshold:
            self._mship_spawned = True
            self._mothership = Mothership(self.level, self._mship_sprite)

    def _update_mothership(self):
        if self._mothership and self._mothership.alive:
            self._mothership.update()

    def _try_mothership_shoot(self):
        if not self._mothership or not self._mothership.alive:
            return
        if len(self.e_bullets) >= self._max_enemy_bullets_for_wave() + 4:
            return
        self._mothership.shoot_cd += 1
        if self._mothership.shoot_cd < self._mothership.shoot_interval:
            return
        self._mothership.shoot_cd = 0
        self.e_bullets.extend(self._mothership.spray_lasers())
        self.sfx.play(self.sfx.enemy_shoot)

    def _jump_to_wave(self, wave):
        self.sfx.stop_intro_music()
        self.sfx.stop_beat()
        self._clear_touch_state()
        self.level = max(1, min(10, wave))
        self._init_level(keep_lives=True)
        self.state = PLAYING

    def update(self):
        for s in self.stars:
            s.update()

        if self.state in (MENU, GAME_OVER):
            self.sfx.start_intro_music()
        else:
            self.sfx.stop_intro_music()

        if self.state == MENU:
            return

        if self.state == LEVEL_CLEAR:
            self.clear_timer -= 1
            for ex in self.explosions:
                ex.update()
            self.explosions = [ex for ex in self.explosions if not ex.done]
            if self.clear_timer <= 0:
                self.level += 1
                if self.level > 10:
                    self.state = WIN
                    if self.score > self.high_score:
                        self.high_score = self.score
                else:
                    self._init_level(keep_lives=True)
                    self.state = PLAYING
            return

        if self.state != PLAYING:
            return

        keys = pygame.key.get_pressed()
        self.player.update(keys, self._touch_state)
        if self._touch_state["fire"]:
            b = self.player.shoot()
            if b:
                self.p_bullets.append(b)
                self.sfx.play(self.sfx.shoot)
        self._update_formation()
        self._update_enemies()
        self._try_dive()
        self._try_enemy_shoot()
        self._update_bullets()
        self._check_bullet_hits()
        self._maybe_spawn_mothership()
        self._update_mothership()
        self._try_mothership_shoot()
        self._check_player_hit()
        for ex in self.explosions:
            ex.update()
        self.explosions = [ex for ex in self.explosions if not ex.done]

        alive_count = len(self._alive())
        mothership_alive = bool(self._mothership and self._mothership.alive)
        self.sfx.update_beat(alive_count + (1 if mothership_alive else 0), self._total_enemies + (1 if self._mship_spawned else 0))

        if alive_count == 0 and not mothership_alive:
            self.sfx.stop_beat()
            self.sfx.play(self.sfx.level_clear)
            self.state       = LEVEL_CLEAR
            self.clear_timer = 150
            for _ in range(25):
                self.explosions.append(Explosion(
                    random.randint(80, SCREEN_W - 80),
                    random.randint(60, SCREEN_H // 2),
                    random.choice([CYAN, MAGENTA, GOLD, GREEN, LIME]),
                    big=True,
                ))

    def _update_formation(self):
        static = self._alive_static()
        if not static:
            return
        xs = [e.home_x + self.fdx for e in static]
        if max(xs) >= SCREEN_W - 45 and self.fdir > 0:
            self.fdir = -1
        elif min(xs) <= 45 and self.fdir < 0:
            self.fdir = 1
        self.fdx += self.fdir * self.fspeed

    def _update_enemies(self):
        for e in self.enemies:
            if e.alive:
                e.update(self.fdx, self.level)

    def _try_dive(self):
        alive  = self._alive()
        static = [e for e in alive if not e.diving and not e.returning]
        divers = sum(1 for e in alive if e.diving)
        max_divers = min(8, 2 + self.level // 2)
        if divers >= max_divers or not static:
            return
        dive_chance = min(0.07, 0.007 + self.level * 0.0024)
        if random.random() < dive_chance:
            random.choice(static).start_dive(self.player.x, self.level)

    def _try_enemy_shoot(self):
        if len(self.e_bullets) >= self._max_enemy_bullets_for_wave():
            return
        self.shoot_timer += 1
        if self.shoot_timer < self.shoot_interval:
            return
        self.shoot_timer = 0
        alive = self._alive()
        if not alive:
            return
        candidates = [e for e in alive if abs(e.x - self.player.x) < 220]
        shooter = random.choice(candidates if candidates else alive)
        vy = 4.0 + self.level * 0.45
        self.e_bullets.append(
            Bullet(shooter.x, shooter.y + shooter.size, vy=vy, is_enemy=True)
        )
        self.sfx.play(self.sfx.enemy_shoot)

    def _update_bullets(self):
        for b in self.p_bullets + self.e_bullets:
            b.update()
        self.p_bullets = [b for b in self.p_bullets if b.alive]
        self.e_bullets = [b for b in self.e_bullets if b.alive]

    def _check_bullet_hits(self):
        alive = self._alive()
        for b in self.p_bullets:
            if not b.alive:
                continue
            for e in alive:
                if e.hitbox().colliderect(b.rect()):
                    b.alive  = False
                    e.alive  = False
                    self.score += e.points()
                    self.explosions.append(Explosion(
                        e.x, e.y,
                        ORANGE if e.etype == BOSS else YELLOW,
                        big=(e.etype == BOSS),
                    ))
                    if e.etype == BOSS:
                        self._trigger_shake(power=8, frames=10)
                        self.sfx.play(self.sfx.explode_big)
                    else:
                        self._trigger_shake(power=5, frames=7)
                        self.sfx.play(self.sfx.explode)
                    break
            if not b.alive:
                continue
            if self._mothership and self._mothership.alive and self._mothership.hitbox().colliderect(b.rect()):
                b.alive = False
                destroyed = self._mothership.take_hit()
                self._trigger_shake(power=6, frames=8)
                if destroyed:
                    self.score += 1200 + self.level * 100
                    self.player.lives += 1
                    self.explosions.append(Explosion(self._mothership.x, self._mothership.y, ORANGE, big=True))
                    self.explosions.append(Explosion(self._mothership.x - 22, self._mothership.y + 6, YELLOW, big=False))
                    self.explosions.append(Explosion(self._mothership.x + 22, self._mothership.y + 6, YELLOW, big=False))
                    self._trigger_shake(power=10, frames=14)
                    self._trigger_flash(alpha=220, decay=52)
                    if not self.sfx.play_oh_yeah():
                        self.sfx.play(self.sfx.explode_big)
                else:
                    self.sfx.play(self.sfx.explode)

    def _check_player_hit(self):
        if self.player.invincible > 0:
            return
        pr = self.player.hitbox()
        for b in self.e_bullets:
            if b.alive and pr.colliderect(b.rect()):
                b.alive = False
                self._hit_player()
                return
        for e in self._alive():
            if e.diving and pr.colliderect(e.hitbox()):
                e.alive = False
                self.explosions.append(Explosion(e.x, e.y, ORANGE, big=True))
                self._hit_player()
                return
        if self._mothership and self._mothership.alive and pr.colliderect(self._mothership.hitbox()):
            self._hit_player()
            return

    def _hit_player(self):
        self.explosions.append(
            Explosion(self.player.x, self.player.y, CYAN, big=True)
        )
        self.sfx.play(self.sfx.player_die)
        self.player.lives -= 1
        if self.player.lives <= 0:
            self.sfx.stop_beat()
            self.state = GAME_OVER
            self._restart_lock_until = pygame.time.get_ticks() + 5000
            if self.score > self.high_score:
                self.high_score = self.score
        else:
            self.player.invincible = 120

    def handle(self, event):
        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            self._handle_touch_event(event)
            if event.type == pygame.FINGERDOWN and self.state in (MENU, GAME_OVER, WIN):
                if self._restart_delay_remaining_ms() > 0:
                    return
                self.sfx.stop_intro_music()
                self._clear_touch_state()
                self._reset()
                self.state = PLAYING
            return

        if event.type != pygame.KEYDOWN:
            return
        k = event.key

        wave = self._wave_from_key(k)
        if wave is not None:
            self._jump_to_wave(wave)
            return

        if self.state == MENU:
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                if self._restart_delay_remaining_ms() > 0:
                    return
                self.sfx.stop_intro_music()
                self._clear_touch_state()
                self._reset()
                self.state = PLAYING
        elif self.state == PLAYING:
            if k == pygame.K_SPACE:
                b = self.player.shoot()
                if b:
                    self.p_bullets.append(b)
                    self.sfx.play(self.sfx.shoot)
            elif k == pygame.K_ESCAPE:
                self.sfx.stop_beat()
                self._clear_touch_state()
                self.state = MENU
        elif self.state in (GAME_OVER, WIN):
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                if self._restart_delay_remaining_ms() > 0:
                    return
                self.sfx.stop_intro_music()
                self._clear_touch_state()
                self._reset()
                self.state = PLAYING
            elif k == pygame.K_ESCAPE:
                self._clear_touch_state()
                self.state = MENU

    def draw(self):
        if self.state in (MENU, GAME_OVER):
            self._draw_start_screen(game_over=(self.state == GAME_OVER))
            pygame.display.flip()
            return

        if getattr(self, '_bg_surf', None) is not None:
            screen.blit(self._bg_surf, (0, 0))
        else:
            screen.fill(BLACK)
        for s in self.stars:
            s.draw(screen)

        for e in self.enemies:
            if e.alive:
                e.draw(screen, self._enemy_sprite_by_size)
        if self._mothership and self._mothership.alive:
            self._mothership.draw(screen)
        for b in self.p_bullets + self.e_bullets:
            b.draw(screen)
        for ex in self.explosions:
            ex.draw(screen)
        if self.player.lives > 0:
            self.player.draw(screen)

        self._draw_hud()
        self._draw_touch_controls()

        if   self.state == GAME_OVER:   self._draw_gameover()
        elif self.state == LEVEL_CLEAR: self._draw_levelclear()
        elif self.state == WIN:         self._draw_win()

        self._draw_flash()
        self._apply_screen_shake()
        pygame.display.flip()

    def _draw_hud(self):
        score_s = self.f_sm.render(f"SCORE  {self.score:07d}", True, WHITE)
        hi_s    = self.f_sm.render(f"BEST   {self.high_score:07d}", True, GOLD)
        lv_s    = self.f_sm.render(f"LEVEL  {self.level:02d}", True, CYAN)
        screen.blit(score_s, (10, 8))
        screen.blit(hi_s,    (SCREEN_W // 2 - hi_s.get_width() // 2, 8))
        screen.blit(lv_s,    (SCREEN_W - lv_s.get_width() - 10, 8))
        if self._mothership and self._mothership.alive:
            ms_s = self.f_sm.render(f"MOTHERSHIP HP  {self._mothership.hp:02d}", True, ORANGE)
            screen.blit(ms_s, (SCREEN_W // 2 - ms_s.get_width() // 2, 34))
        for i in range(self.player.lives):
            draw_ship(screen, 18 + i * 30, SCREEN_H - 18, size=11)
        pygame.draw.line(
            screen, DIM_BLUE, (0, SCREEN_H - 36), (SCREEN_W, SCREEN_H - 36)
        )

    def _draw_touch_controls(self):
        if self.state != PLAYING:
            return
        if not (self._show_touch_controls or self._touch_seen):
            return

        left, right, fire = self._touch_buttons()
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        def draw_button(rect, label, active):
            fill = (40, 180, 255, 140) if active else (20, 50, 90, 95)
            border = (170, 230, 255, 230) if active else (100, 160, 220, 180)
            pygame.draw.rect(overlay, fill, rect, border_radius=16)
            pygame.draw.rect(overlay, border, rect, width=2, border_radius=16)
            txt = self.f_sm.render(label, True, WHITE)
            tx = rect.centerx - txt.get_width() // 2
            ty = rect.centery - txt.get_height() // 2
            overlay.blit(txt, (tx, ty))

        draw_button(left, "LEFT", self._touch_state["left"])
        draw_button(right, "RIGHT", self._touch_state["right"])
        draw_button(fire, "FIRE", self._touch_state["fire"])
        screen.blit(overlay, (0, 0))

    def _draw_start_screen(self, game_over=False):
        if self._start_screen is not None:
            screen.blit(self._start_screen, (0, 0))
        else:
            screen.fill(BLACK)

        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 96))
        screen.blit(shade, (0, 0))

        title = "GAME  OVER" if game_over else "GALAMAX"
        title_color = RED if game_over else GOLD
        t = self.f_big.render(title, True, title_color)
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 74))

        score_s = self.f_med.render(f"SCORE   {self.score:07d}", True, WHITE)
        best_s  = self.f_med.render(f"HIGH SCORE   {self.high_score:07d}", True, GOLD)
        screen.blit(score_s, (SCREEN_W // 2 - score_s.get_width() // 2, 170))
        screen.blit(best_s,  (SCREEN_W // 2 - best_s.get_width() // 2, 220))

        remaining = self._restart_delay_remaining_ms()
        if game_over and remaining > 0:
            wait_s = self.f_sm.render(f"RESTART AVAILABLE IN {remaining / 1000:.1f}s", True, ORANGE)
            screen.blit(wait_s, (SCREEN_W // 2 - wait_s.get_width() // 2, 278))

        if remaining <= 0 and (pygame.time.get_ticks() // 500) % 2 == 0:
            go = self.f_med.render("PRESS  SPACE  TO  START", True, GREEN)
            screen.blit(go, (SCREEN_W // 2 - go.get_width() // 2, 500))

        ctrl = self.f_sm.render("ARROWS / WASD MOVE   SPACE FIRE", True, WHITE)
        screen.blit(ctrl, (SCREEN_W // 2 - ctrl.get_width() // 2, 548))

    def _draw_menu(self):
        t = self.f_big.render("GALAMAX", True, GOLD)
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 70))

        sub = self.f_med.render("SPACE  DEFENDER", True, CYAN)
        screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 138))

        table = [
            (draw_bee,       "=   50 / 100 pts",  YELLOW),
            (draw_butterfly, "=   80 / 160 pts",  MAGENTA),
            (draw_boss,      "=  150 / 300 pts",  RED),
        ]
        for i, (fn, label, col) in enumerate(table):
            iy = 230 + i * 62
            fn(screen, SCREEN_W // 2 - 130, iy, 18)
            ls = self.f_sm.render(label, True, col)
            screen.blit(ls, (SCREEN_W // 2 - 95, iy - 9))

        note = self.f_sm.render(
            "(double points when hitting a diving enemy)", True, (160, 160, 160)
        )
        screen.blit(note, (SCREEN_W // 2 - note.get_width() // 2, 420))

        ctrl = self.f_sm.render(
            "\u2190\u2192 / A D  Move      SPACE  Fire      ESC  Menu",
            True, WHITE,
        )
        screen.blit(ctrl, (SCREEN_W // 2 - ctrl.get_width() // 2, 460))

        if (pygame.time.get_ticks() // 500) % 2 == 0:
            go = self.f_med.render("PRESS  SPACE  TO  START", True, GREEN)
            screen.blit(go, (SCREEN_W // 2 - go.get_width() // 2, 510))

        if self.high_score:
            hs = self.f_sm.render(f"HIGH SCORE  {self.high_score:07d}", True, GOLD)
            screen.blit(hs, (SCREEN_W // 2 - hs.get_width() // 2, 564))

    def _draw_gameover(self):
        self._dim_overlay()
        go = self.f_big.render("GAME  OVER", True, RED)
        screen.blit(go, (SCREEN_W // 2 - go.get_width() // 2, 170))
        sc = self.f_med.render(f"SCORE   {self.score:07d}", True, WHITE)
        screen.blit(sc, (SCREEN_W // 2 - sc.get_width() // 2, 265))
        if self.score and self.score >= self.high_score:
            nh = self.f_med.render("NEW  HIGH  SCORE!", True, GOLD)
            screen.blit(nh, (SCREEN_W // 2 - nh.get_width() // 2, 315))
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            r = self.f_med.render(
                "SPACE  to retry      ESC  for menu", True, GREEN
            )
            screen.blit(r, (SCREEN_W // 2 - r.get_width() // 2, 410))

    def _draw_levelclear(self):
        lc = self.f_big.render(f"LEVEL  {self.level}  CLEAR!", True, CYAN)
        screen.blit(lc, (SCREEN_W // 2 - lc.get_width() // 2, 220))
        if self.level < 10:
            nxt = self.f_med.render(
                f"Preparing level {self.level + 1} ...", True, WHITE
            )
            screen.blit(nxt, (SCREEN_W // 2 - nxt.get_width() // 2, 300))

    def _draw_win(self):
        self._dim_overlay()
        w = self.f_big.render("YOU  WIN!", True, GOLD)
        screen.blit(w, (SCREEN_W // 2 - w.get_width() // 2, 150))
        sc = self.f_med.render(f"FINAL SCORE   {self.score:07d}", True, WHITE)
        screen.blit(sc, (SCREEN_W // 2 - sc.get_width() // 2, 250))
        hs = self.f_med.render(f"HIGH  SCORE   {self.high_score:07d}", True, GOLD)
        screen.blit(hs, (SCREEN_W // 2 - hs.get_width() // 2, 300))
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            ag = self.f_med.render(
                "SPACE  play again      ESC  menu", True, GREEN
            )
            screen.blit(ag, (SCREEN_W // 2 - ag.get_width() // 2, 410))

    def _dim_overlay(self):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        screen.blit(dim, (0, 0))


# ---------------------------------------------------------------------------
# Async entry point  (required by pygbag / WebAssembly)
# ---------------------------------------------------------------------------

async def main():
    game = Game()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle(event)
        game.update()
        game.draw()
        clock.tick(FPS)
        await asyncio.sleep(0)   # yield control back to the browser event loop

    pygame.quit()


asyncio.run(main())
