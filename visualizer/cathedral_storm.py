"""
Cathedral in the Storm — Audio Visualizer
==========================================
Layers (back to front):
  1. Storm sky gradient
  2. Falling rain streaks
  3. Ground / cobblestones
  4. Puddles with colored reflections + ripple rings
  5. Cathedral silhouette
  6. Stained glass rose window (logo + radial frequency segments)
  7. Arched side windows glowing
  8. Light spill cones from windows onto ground
  9. Spectrum bars (bottom)
  10. Branding text
  11. Lightning flash overlay
"""

import pygame
import numpy as np
import random
import math
import os
from PIL import Image


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
PALETTE_BASE   = (15,  8,  30)   # Near-black purple sky
PALETTE_ACCENT = (50, 30,  90)   # Deep violet
CYAN           = (0,  200, 255)
MAGENTA        = (180,  0, 255)
BLUE           = (30,  80, 255)
GOLD           = (255, 180,  30)
WHITE          = (255, 255, 255)
RAIN_COLOUR    = (120, 140, 180, 80)   # RGBA semi-transparent

WINDOW_COLOURS = [
    (0,   180, 255),   # Cyan
    (160,  0,  255),   # Purple
    (0,   255, 160),   # Teal
    (255,  60, 180),   # Magenta-pink
    (80,  120, 255),   # Indigo
    (255, 200,   0),   # Gold
]


def lerp_colour(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ---------------------------------------------------------------------------
# Rain
# ---------------------------------------------------------------------------
class RainDrop:
    def __init__(self, width, height):
        self.reset(width, height)

    def reset(self, width, height):
        self.x = random.randint(0, width)
        self.y = random.randint(-height, 0)
        self.length = random.randint(10, 30)
        self.speed  = random.uniform(8, 18)
        self.alpha  = random.randint(40, 120)

    def update(self, width, height, speed_mult: float):
        self.y += self.speed * speed_mult
        self.x -= self.speed * speed_mult * 0.15   # slight diagonal
        if self.y > height + self.length:
            self.reset(width, height)

    def draw(self, surf, light_tint=(120, 140, 180)):
        x1, y1 = int(self.x), int(self.y)
        x2 = int(self.x - self.length * 0.15)
        y2 = int(self.y + self.length)
        pygame.draw.line(surf, (*light_tint, self.alpha), (x1, y1), (x2, y2), 1)


# ---------------------------------------------------------------------------
# Puddle
# ---------------------------------------------------------------------------
class Puddle:
    def __init__(self, cx, cy, rx, ry):
        self.cx, self.cy = cx, cy
        self.rx, self.ry = rx, ry
        self.ripples: list[dict] = []
        self.colour = (30, 60, 120)

    def trigger_ripple(self):
        self.ripples.append({"r": 0, "alpha": 180, "max_r": self.rx * 0.8})

    def update(self):
        for rip in self.ripples:
            rip["r"]     += 1.2
            rip["alpha"] -= 4
        self.ripples = [r for r in self.ripples if r["alpha"] > 0]

    def draw(self, surf, colour, intensity: float):
        # Puddle base (ellipse)
        tinted = lerp_colour((10, 10, 20), colour, intensity * 0.6)
        rect = pygame.Rect(self.cx - self.rx, self.cy - self.ry,
                           self.rx * 2, self.ry * 2)
        pygame.draw.ellipse(surf, tinted, rect)
        pygame.draw.ellipse(surf, (40, 40, 60), rect, 1)

        # Ripple rings
        for rip in self.ripples:
            if rip["r"] > self.rx * 0.8:
                continue
            alpha = int(rip["alpha"])
            col   = (*colour, alpha)
            rip_rx = int(rip["r"])
            rip_ry = max(1, int(rip["r"] * self.ry / self.rx))
            rip_rect = pygame.Rect(self.cx - rip_rx, self.cy - rip_ry,
                                   rip_rx * 2, rip_ry * 2)
            tmp = pygame.Surface((rip_rx * 2 + 2, rip_ry * 2 + 2), pygame.SRCALPHA)
            pygame.draw.ellipse(tmp, col,
                                pygame.Rect(1, 1, rip_rx * 2, rip_ry * 2), 2)
            surf.blit(tmp, (self.cx - rip_rx - 1, self.cy - rip_ry - 1))


# ---------------------------------------------------------------------------
# Main Visualizer
# ---------------------------------------------------------------------------
class CathedralStormVisualizer:
    W, H = 1920, 1080

    def __init__(self, analyzer, logo_path: str):
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.W, self.H), pygame.NOFRAME
        )
        pygame.display.set_caption("Cathedral in the Storm — AVizualizer")

        self.analyzer   = analyzer
        self.clock      = pygame.time.Clock()
        self.running    = True
        self.recording  = False

        # Rain
        N_DROPS = 700
        self.drops = [RainDrop(self.W, self.H) for _ in range(N_DROPS)]

        # Puddles — scattered across the lower third
        self.puddles = [
            Puddle(300,  900, 90, 25),
            Puddle(600,  940, 60, 16),
            Puddle(1000, 910, 110, 28),
            Puddle(1400, 930, 75, 20),
            Puddle(1650, 900, 55, 14),
        ]

        # Lightning flash state
        self.flash_alpha  = 0
        self.flash_colour = (255, 255, 255)

        # Window glow state
        self.window_glow   = [0.0] * 6   # 6 stained glass segments
        self.side_glow_l   = 0.0
        self.side_glow_r   = 0.0

        # Load & pre-process logo
        self._load_logo(logo_path)

        # Pre-build cathedral silhouette surface
        self.cathedral_surf = self._build_cathedral()

        # Font
        pygame.font.init()
        self.font_brand = pygame.font.SysFont("Georgia", 36, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 20)

        # Reusable alpha surfaces
        self.rain_surf  = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.light_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.flash_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)

        # Internal playback position tracker
        self._pos_seconds = 0.0
        self._recorder      = None

    # ------------------------------------------------------------------
    # Asset loading
    # ------------------------------------------------------------------
    def _load_logo(self, path: str):
        """Load cross logo, convert to pygame surface with alpha."""
        img = Image.open(path).convert("RGBA")
        # Scale to fit rose window area (~300x300)
        size = 280
        img  = img.resize((size, size), Image.LANCZOS)
        raw  = img.tobytes()
        self.logo_surf = pygame.image.fromstring(raw, img.size, "RGBA").convert_alpha()
        self.logo_size = size

    def _build_cathedral(self) -> pygame.Surface:
        """Draws the gothic cathedral silhouette onto a surface."""
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        cx   = self.W // 2
        col  = (12, 8, 20, 255)   # Very dark, near-black

        # ---- Main nave (central tower body) ----
        nave_rect = pygame.Rect(cx - 200, 200, 400, 700)
        pygame.draw.rect(surf, col, nave_rect)

        # Nave roof (pointed arch / gable)
        roof_pts = [(cx - 200, 200), (cx, 60), (cx + 200, 200)]
        pygame.draw.polygon(surf, col, roof_pts)

        # ---- Left transept ----
        l_rect = pygame.Rect(cx - 480, 380, 280, 520)
        pygame.draw.rect(surf, col, l_rect)
        l_roof = [(cx - 480, 380), (cx - 340, 250), (cx - 200, 380)]
        pygame.draw.polygon(surf, col, l_roof)

        # ---- Right transept ----
        r_rect = pygame.Rect(cx + 200, 380, 280, 520)
        pygame.draw.rect(surf, col, r_rect)
        r_roof = [(cx + 200, 380), (cx + 340, 250), (cx + 480, 380)]
        pygame.draw.polygon(surf, col, r_roof)

        # ---- Left bell tower ----
        pygame.draw.rect(surf, col, pygame.Rect(cx - 620, 180, 120, 720))
        lt_roof = [(cx - 620, 180), (cx - 560, 80), (cx - 500, 180)]
        pygame.draw.polygon(surf, col, lt_roof)

        # ---- Right bell tower ----
        pygame.draw.rect(surf, col, pygame.Rect(cx + 500, 180, 120, 720))
        rt_roof = [(cx + 500, 180), (cx + 560, 80), (cx + 620, 180)]
        pygame.draw.polygon(surf, col, rt_roof)

        # ---- Ground / base ----
        pygame.draw.rect(surf, (8, 5, 15, 255),
                         pygame.Rect(0, 880, self.W, self.H - 880))

        return surf

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _draw_sky(self, surf, rms: float):
        brightness = int(10 + rms * 20)
        sky_top    = (brightness, brightness // 2, brightness * 2)
        sky_bot    = (brightness * 2, brightness, brightness * 3 + 10)
        for y in range(self.H // 2):
            t   = y / (self.H / 2)
            col = lerp_colour(sky_top, sky_bot, t)
            pygame.draw.line(surf, col, (0, y), (self.W, y))

    def _draw_ground(self, surf):
        # Dark cobblestone ground gradient
        for y in range(850, self.H):
            t   = (y - 850) / (self.H - 850)
            col = lerp_colour((12, 8, 18), (5, 3, 10), t)
            pygame.draw.line(surf, col, (0, y), (self.W, y))

    def _draw_light_spill(self, surf, bass: float, spectrum: np.ndarray):
        """Colored light cones spilling from stained-glass windows onto ground."""
        cx = self.W // 2
        self.light_surf.fill((0, 0, 0, 0))

        # Central rose window spill — cone downward
        avg_energy = float(np.mean(spectrum))
        dominant   = WINDOW_COLOURS[int(avg_energy * (len(WINDOW_COLOURS) - 1))]
        alpha      = int(avg_energy * 60)
        if alpha > 5:
            pts = [(cx - 180, 520), (cx + 180, 520),
                   (cx + 350, 880), (cx - 350, 880)]
            tmp_col = (*dominant, alpha)
            pygame.draw.polygon(self.light_surf, tmp_col, pts)

        # Side window spills
        # Left
        la = int(self.side_glow_l * 50)
        if la > 3:
            l_col = (*WINDOW_COLOURS[1], la)
            pygame.draw.polygon(self.light_surf, l_col,
                [(cx - 420, 540), (cx - 340, 540),
                 (cx - 250, 880), (cx - 500, 880)])
        # Right
        ra = int(self.side_glow_r * 50)
        if ra > 3:
            r_col = (*WINDOW_COLOURS[0], ra)
            pygame.draw.polygon(self.light_surf, r_col,
                [(cx + 340, 540), (cx + 420, 540),
                 (cx + 500, 880), (cx + 250, 880)])

        surf.blit(self.light_surf, (0, 0))

    def _draw_rose_window(self, surf, spectrum: np.ndarray, bass: float):
        """Stained-glass rose window with logo center."""
        cx, cy = self.W // 2, 420
        outer_r = 160
        inner_r = 70      # Logo occupies this zone

        # Draw radial segments (petals) colored by frequency
        n_seg     = len(WINDOW_COLOURS)
        bands     = np.array_split(spectrum, n_seg)
        seg_angle = 360 / n_seg

        for i, (band_vals, colour) in enumerate(zip(bands, WINDOW_COLOURS)):
            energy = float(band_vals.mean())
            self.window_glow[i] = self.window_glow[i] * 0.85 + energy * 0.15  # Smooth

            if self.window_glow[i] < 0.02:
                continue
            alpha = int(self.window_glow[i] * 220)
            col   = (*colour, alpha)

            start_angle = math.radians(i * seg_angle - 90)
            end_angle   = math.radians((i + 1) * seg_angle - 90)
            N_pts       = 20

            pts = [(int(cx + inner_r * math.cos(start_angle)),
                    int(cy + inner_r * math.sin(start_angle)))]
            for k in range(N_pts + 1):
                a = start_angle + (end_angle - start_angle) * k / N_pts
                pts.append((int(cx + outer_r * math.cos(a)),
                             int(cy + outer_r * math.sin(a))))
            pts.append((int(cx + inner_r * math.cos(end_angle)),
                         int(cy + inner_r * math.sin(end_angle))))

            tmp = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            pygame.draw.polygon(tmp, col, pts)
            surf.blit(tmp, (0, 0))

        # Outer ring
        pygame.draw.circle(surf, (50, 40, 80), (cx, cy), outer_r, 3)
        pygame.draw.circle(surf, (30, 20, 60), (cx, cy), inner_r + 2, 2)

        # Glow halo (bass-driven)
        halo_r = int(outer_r + bass * 40)
        halo_a = int(bass * 80)
        if halo_a > 5:
            pygame.draw.circle(surf, (*CYAN, halo_a), (cx, cy), halo_r, 4)

        # Logo center
        logo_x = cx - self.logo_size // 2
        logo_y = cy - self.logo_size // 2
        surf.blit(self.logo_surf, (logo_x, logo_y))

    def _draw_side_windows(self, surf, mid: float, treble: float):
        """Arched gothic windows on the side transepts."""
        cx = self.W // 2
        self.side_glow_l = self.side_glow_l * 0.8 + mid    * 0.2
        self.side_glow_r = self.side_glow_r * 0.8 + treble * 0.2

        windows = [
            # (center_x, center_y, w, h, glow, colour)
            (cx - 380, 490, 60, 100, self.side_glow_l, WINDOW_COLOURS[1]),
            (cx + 380, 490, 60, 100, self.side_glow_r, WINDOW_COLOURS[0]),
        ]
        for wx, wy, ww, wh, glow, col in windows:
            if glow < 0.02:
                continue
            alpha = int(glow * 200)
            tmp   = pygame.Surface((ww, wh), pygame.SRCALPHA)
            pygame.draw.ellipse(tmp, (*col, alpha), tmp.get_rect())
            surf.blit(tmp, (wx - ww // 2, wy - wh // 2))

    def _draw_spectrum_bars(self, surf, spectrum: np.ndarray):
        """Symmetric spectrum bars at the bottom of the screen."""
        n     = len(spectrum)
        bar_w = self.W // (n * 2 + 4)
        max_h = 120
        cx    = self.W // 2

        for i, val in enumerate(spectrum):
            h    = int(val * max_h)
            t    = i / n
            col  = lerp_colour(CYAN, MAGENTA, t)

            # Right side
            x_r = cx + i * (bar_w + 2) + 4
            pygame.draw.rect(surf, col,
                             pygame.Rect(x_r, self.H - 160 - h, bar_w, h))
            # Left mirror
            x_l = cx - (i + 1) * (bar_w + 2) - 4
            pygame.draw.rect(surf, col,
                             pygame.Rect(x_l, self.H - 160 - h, bar_w, h))

            # Glow cap
            if h > 5:
                cap_col = lerp_colour(col, WHITE, 0.6)
                pygame.draw.rect(surf, cap_col,
                                 pygame.Rect(x_r, self.H - 160 - h - 2, bar_w, 3))
                pygame.draw.rect(surf, cap_col,
                                 pygame.Rect(x_l, self.H - 160 - h - 2, bar_w, 3))

    def _draw_branding(self, surf):
        txt = self.font_brand.render("Modern Christian Rock Music", True, (160, 120, 220))
        glow_txt = self.font_brand.render("Modern Christian Rock Music", True, (80, 0, 160))
        x = (self.W - txt.get_width()) // 2
        y = self.H - 60
        surf.blit(glow_txt, (x + 2, y + 2))
        surf.blit(txt, (x, y))

    def _trigger_lightning(self):
        self.flash_alpha  = random.randint(120, 220)
        self.flash_colour = random.choice([
            (255, 255, 255), (200, 180, 255), (180, 220, 255)
        ])

    def _draw_flash(self, surf):
        if self.flash_alpha <= 0:
            return
        self.flash_surf.fill((*self.flash_colour, self.flash_alpha))
        surf.blit(self.flash_surf, (0, 0))
        self.flash_alpha = max(0, self.flash_alpha - 18)

    def _draw_rain(self, surf, rms: float, rain_tint=(120, 140, 180)):
        """Draw all rain drops and tint them based on window light."""
        self.rain_surf.fill((0, 0, 0, 0))
        speed_mult = 0.7 + rms * 1.5
        for drop in self.drops:
            drop.update(self.W, self.H, speed_mult)
            drop.draw(self.rain_surf, rain_tint)
        surf.blit(self.rain_surf, (0, 0))

    # ------------------------------------------------------------------
    # Main render frame
    # ------------------------------------------------------------------
    def render_frame(self, pos_seconds: float):
        frame_idx = self.analyzer.get_frame_index(pos_seconds)
        spectrum  = self.analyzer.get_spectrum(frame_idx, n_bands=48)
        bass, mid, treble = self.analyzer.get_bass_mid_treble(frame_idx)
        rms       = self.analyzer.get_rms(frame_idx)
        is_beat   = self.analyzer.is_beat(frame_idx)
        onset     = self.analyzer.get_onset_strength(frame_idx)

        surf = self.screen

        # --- 1. Sky ---
        self._draw_sky(surf, rms)

        # --- 2. Ground ---
        self._draw_ground(surf)

        # --- 3. Light spill (behind silhouette) ---
        self._draw_light_spill(surf, bass, spectrum)

        # --- 4. Cathedral silhouette ---
        surf.blit(self.cathedral_surf, (0, 0))

        # --- 5. Rose window ---
        self._draw_rose_window(surf, spectrum, bass)

        # --- 6. Side windows ---
        self._draw_side_windows(surf, mid, treble)

        # --- 7. Rain ---
        # Tint rain based on dominant window colour
        avg_energy = float(spectrum.mean())
        tint_col   = lerp_colour((100, 120, 160),
                                  WINDOW_COLOURS[int(avg_energy * 5)],
                                  min(avg_energy * 1.5, 0.5))
        self._draw_rain(surf, rms, tint_col)

        # --- 8. Puddles ---
        if is_beat:
            for p in random.sample(self.puddles, k=random.randint(1, 3)):
                p.trigger_ripple()
        for p in self.puddles:
            p.update()
            beat_col = WINDOW_COLOURS[int(bass * 5)]
            p.draw(surf, beat_col, rms)

        # --- 9. Spectrum bars ---
        self._draw_spectrum_bars(surf, spectrum)

        # --- 10. Branding ---
        self._draw_branding(surf)

        # --- 11. Lightning flash ---
        if onset > 0.85 and random.random() < 0.25:
            self._trigger_lightning()
        self._draw_flash(surf)

        pygame.display.flip()
        return surf

    # ------------------------------------------------------------------
    # Run loop (called from launcher after everything is set up)
    # ------------------------------------------------------------------
    def run(self, audio_start_fn, recorder=None):
        """
        audio_start_fn  : callable that starts audio playback and returns
                          a function get_pos() → float (seconds)
        recorder        : VideoRecorder instance (or None for preview).
        """
        self._recorder = recorder
        get_pos        = audio_start_fn()

        self.clock.tick()  # Reset clock before loop

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

            pos = get_pos()
            if pos is None or pos >= self.analyzer.duration:
                self.running = False
                break

            frame_surf = self.render_frame(pos)

            if recorder:
                recorder.write_frame(frame_surf)

            self.clock.tick(60)

        if recorder:
            recorder.stop()

        pygame.quit()
