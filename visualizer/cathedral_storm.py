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
    # Full render resolution (written to video)
    W, H = 1920, 1080
    # Preview window size (what the user sees on screen)
    PW, PH = 1280, 720

    def __init__(self, analyzer, logo_path: str):
        pygame.init()
        # Windowed preview display — normal window with title bar
        self.screen = pygame.display.set_mode((self.PW, self.PH))
        pygame.display.set_caption("Cathedral in the Storm — AVizualizer  [Preview]")

        # Full-resolution offscreen canvas — this is what gets recorded
        self.canvas = pygame.Surface((self.W, self.H))

        self.analyzer   = analyzer
        self.clock      = pygame.time.Clock()
        self.running    = True
        self.status_callback = None
        self.recording  = False

        # Rain
        N_DROPS = 700
        self.drops = [RainDrop(self.W, self.H) for _ in range(N_DROPS)]

        # Puddles — shifted lower toward the bottom of the screen
        self.puddles = [
            Puddle(300,  990, 90, 25),
            Puddle(600,  1010, 60, 16),
            Puddle(1000, 995, 110, 28),
            Puddle(1400, 1005, 75, 20),
            Puddle(1650, 990, 55, 14),
        ]

        # Lightning flash state
        self.flash_alpha  = 0
        self.flash_colour = (255, 255, 255)
        
        # Lightning Bolt state
        self.bolt_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.bolt_alpha = 0
        self.next_bolt_time = random.uniform(15, 20)

        # Window glow and pulse state
        self.window_glow   = [0.0] * 6   # 6 stained glass segments
        self.side_glow_l   = 0.0
        self.side_glow_r   = 0.0
        self.rose_pulse    = 0.0
        self.bass_avg      = 0.0

        # Load & pre-process logo
        self._load_logo(logo_path)

        # Load image assets
        self._load_assets()

        # Pre-build cathedral silhouette surface
        self.cathedral_surf = self._build_cathedral()

        # Font
        pygame.font.init()
        self.font_brand = pygame.font.SysFont("Georgia", 36, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 20)

        # Reusable alpha surfaces (drawn at full canvas resolution)
        self.rain_surf  = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.light_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.flash_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)

        # Internal playback position tracker
        self._pos_seconds = 0.0
        self._recorder      = None

        # Fog drift state
        self.fog_x = 0.0

    # ------------------------------------------------------------------
    # Asset loading
    # ------------------------------------------------------------------
    def _load_logo(self, path: str):
        """Load cross logo, convert to pygame surface with alpha."""
        img = Image.open(path).convert("RGBA")
        size = 280
        img  = img.resize((size, size), Image.LANCZOS)
        raw  = img.tobytes()
        self.logo_surf = pygame.image.fromstring(raw, img.size, "RGBA").convert_alpha()
        self.logo_size = size

    def _load_assets(self):
        """Load and pre-scale all PNG background assets with correct transparency."""
        assets = os.path.join(os.path.dirname(__file__), "..", "assets")

        def pil_to_pygame(img: Image.Image) -> pygame.Surface:
            raw = img.tobytes()
            return pygame.image.fromstring(raw, img.size, "RGBA").convert_alpha()

        def load_scaled_rgba(fname, w, h) -> Image.Image:
            path = os.path.join(assets, fname)
            img  = Image.open(path).convert("RGBA")
            return img.resize((w, h), Image.LANCZOS)

        # --- Storm sky: just scale, keep as-is ---
        sky_img = load_scaled_rgba("storm_sky.png", self.W, self.H)
        self.sky_surf = pil_to_pygame(sky_img)

        # --- Cathedral silhouette: REMOVE white/grey background, keep dark pixels only ---
        cat_img = load_scaled_rgba("cathedral_silhouette.png", self.W, self.H)
        cat_arr = np.array(cat_img)
        # Brightness of each pixel (max of R,G,B)
        brightness = cat_arr[:, :, :3].max(axis=2)
        # Make bright pixels (background) fully transparent; dark pixels opaque
        cat_arr[:, :, 3] = np.where(brightness > 100, 0, 255)
        
        # --- Apply linear alpha gradient to the bottom 10% ---
        grad_h = int(self.H * 0.1)
        for y in range(self.H - grad_h, self.H):
            # calculate multiplier (0.0 at bottom-most pixel, 1.0 at start of gradient zone)
            alpha_mult = (self.H - 1 - y) / (grad_h - 1)
            cat_arr[y, :, 3] = (cat_arr[y, :, 3] * alpha_mult).astype(np.uint8)

        # Recolor dark pixels to near-black with a slight blue tint
        mask = brightness <= 100
        cat_arr[mask, 0] = 10
        cat_arr[mask, 1] = 6
        cat_arr[mask, 2] = 18
        self.cathedral_surf = pil_to_pygame(Image.fromarray(cat_arr, "RGBA"))

        # --- Rose window + cross: load both bright and dark versions ---
        rw_size = 400   # display size on canvas (pixels)
        
        def load_masked_rose(filename):
            img = load_scaled_rgba(filename, rw_size, rw_size)
            arr = np.array(img)
            # Apply circular alpha mask
            cy_img, cx_img = rw_size // 2, rw_size // 2
            ys, xs = np.ogrid[:rw_size, :rw_size]
            dist = np.sqrt((xs - cx_img)**2 + (ys - cy_img)**2)
            outside_circle = dist > (rw_size // 2 - 2)
            arr[outside_circle, 3] = 0
            return pil_to_pygame(Image.fromarray(arr, "RGBA"))

        self.rose_window_bright = load_masked_rose("rose_window_cross.png")
        self.rose_window_dark   = load_masked_rose("rose_window_crossDark.png")
        self.rose_window_size   = rw_size

        # --- Cobblestone ground: Wide strip texture ---
        ground_h = self.H - 840
        ground_img = load_scaled_rgba("cobblestone_ground.png", self.W, ground_h)
        self.ground_surf = pil_to_pygame(ground_img)

        # Pre-darken ground image
        dark = pygame.Surface((self.W, ground_h), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 160))
        self.ground_surf.blit(dark, (0, 0))

        # --- Storm Fog: remove black background, keep white mist ---
        # Anchor point: we want the fog to start slightly above the ground (840) to cover the church base,
        # and span exactly to the bottom of the screen (1080).
        self.church_base_y = 780 
        self.fog_h = self.H - self.church_base_y
        self.fog_w = self.W

        fog_img = load_scaled_rgba("storm_fog.png", self.fog_w, self.fog_h)
        fog_arr = np.array(fog_img)
        
        # Use brightness as alpha - increased density for better masking
        brightness_fog = fog_arr[:, :, :3].max(axis=2)
        fog_arr[:, :, 3] = np.clip(brightness_fog * 1.2, 0, 255).astype(np.uint8)
        
        # Tint slightly blue-purple
        mask_fog = brightness_fog > 0
        fog_arr[mask_fog, 0] = (fog_arr[mask_fog, 0] * 0.4).astype(np.uint8)
        fog_arr[mask_fog, 1] = (fog_arr[mask_fog, 1] * 0.4).astype(np.uint8)
        fog_arr[mask_fog, 2] = (fog_arr[mask_fog, 2] * 0.6).astype(np.uint8)
        
        self.fog_surf = pil_to_pygame(Image.fromarray(fog_arr, "RGBA"))

        # --- Side window image ---
        side_img = load_scaled_rgba("side_window_stained.png", 60, 140)
        self.side_window_surf = pil_to_pygame(side_img)

        # --- Lightning Overlay ---
        lightning_img = load_scaled_rgba("lightning_overlay.png", self.W, self.H)
        self.lightning_overlay = pil_to_pygame(lightning_img)


        print("[Assets] All image assets loaded and processed.")

    def _build_cathedral(self) -> pygame.Surface:
        """Returns the pre-processed transparent cathedral silhouette (built in _load_assets)."""
        return self.cathedral_surf


    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _draw_sky(self, surf, rms: float):
        """Blit the storm sky PNG, brightening slightly with loudness."""
        surf.blit(self.sky_surf, (0, 0))
        
        # Jaged Lightning Bolt + Cloud Glow Overlay
        if self.bolt_alpha > 0:
            # 1. First, blit the cinematic cloud glow (The "Boom of Light")
            # We fade it out a bit slower than the harsh flash
            overlay_alpha = min(255, self.bolt_alpha * 1.2)
            self.lightning_overlay.set_alpha(int(overlay_alpha))
            surf.blit(self.lightning_overlay, (0, 0))

            # 2. Then, blit the jagged bolt core on top
            self.bolt_surf.set_alpha(self.bolt_alpha)
            surf.blit(self.bolt_surf, (0, 0))
            
            self.bolt_alpha = max(0, self.bolt_alpha - 12) # Fade out smoothly

        # Subtle brightness pulse with RMS — overlay a semi-transparent layer
        if rms > 0.05:
            bright = pygame.Surface((self.W, self.H // 2), pygame.SRCALPHA)
            bright.fill((30, 10, 60, int(rms * 40)))
            surf.blit(bright, (0, 0))

    def _draw_ground(self, surf):
        """Draw the wide cobblestone texture across the lower ground strip."""
        surf.blit(self.ground_surf, (0, 840))


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
        """Stained-glass rose window — animated colour segments behind the combined image."""
        cx, cy  = self.W // 2, 420
        outer_r = self.rose_window_size // 2   # matches the image radius
        inner_r = 60

        # --- Animated colour segments (drawn BEHIND the image) ---
        n_seg     = len(WINDOW_COLOURS)
        bands     = np.array_split(spectrum, n_seg)
        seg_angle = 360 / n_seg

        for i, (band_vals, colour) in enumerate(zip(bands, WINDOW_COLOURS)):
            energy = float(band_vals.mean())
            self.window_glow[i] = self.window_glow[i] * 0.85 + energy * 0.15

            if self.window_glow[i] < 0.02:
                continue
            alpha = int(self.window_glow[i] * 200)
            col   = (*colour, alpha)

            start_angle = math.radians(i * seg_angle - 90)
            end_angle   = math.radians((i + 1) * seg_angle - 90)
            N_pts = 20

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

        # --- Glow halo behind the window (bass-driven soft gradient) ---
        halo_r = int(outer_r + bass * 50)
        halo_a = int(bass * 90)
        if halo_a > 5:
            halo_surf = pygame.Surface((halo_r * 2, halo_r * 2), pygame.SRCALPHA)
            # Draw concentric circles fading out to create soft edge
            for r in range(outer_r, halo_r, 3):
                a = int(halo_a * (1.0 - (r - outer_r) / (halo_r - outer_r)))
                pygame.draw.circle(halo_surf, (*CYAN, a), (halo_r, halo_r), r, 4)
            surf.blit(halo_surf, (cx - halo_r, cy - halo_r))

        # --- Combined rose window + cross image on top ---
        img_x = cx - self.rose_window_size // 2
        img_y = cy - self.rose_window_size // 2
        
        # Draw the dark base image always
        surf.blit(self.rose_window_dark, (img_x, img_y))
        
        # --- Hard Envelope Filter for Rose Window ---
        # 1. Trigger Pulse:
        # - Hard Threshold Gate: Ignore anything below 85% of max possible sub-bass intensity
        if bass > 0.85:
            self.rose_pulse = 255.0  # Instant attack/Peak flash
            
        # 2. Aggressive Release (Instant strobe effect)
        # Drop to zero in ~2-3 frames (at 60fps)
        self.rose_pulse = max(0, self.rose_pulse - 100) 

        pulse_alpha = int(self.rose_pulse)
        if pulse_alpha > 5:
            self.rose_window_bright.set_alpha(pulse_alpha)
            surf.blit(self.rose_window_bright, (img_x, img_y))


    def _draw_side_windows(self, surf, mid: float, treble: float):
        """Arched gothic windows tied to snare and hi-hats."""
        cx = self.W // 2
        # Fast decay (0.4 multiplier) for quick flashing/strobing effect
        self.side_glow_l = self.side_glow_l * 0.4 + mid    * 0.6  # Snare
        self.side_glow_r = self.side_glow_r * 0.4 + treble * 0.6  # Hi-hat

        windows = [
            # (center_x, bottom_y, w, h, glow, colour)
            (cx - 380, 540, 60, 140, self.side_glow_l, WINDOW_COLOURS[1]),
            (cx + 380, 540, 60, 140, self.side_glow_r, WINDOW_COLOURS[0]),
        ]
        for wx, wy, ww, wh, glow, col in windows:
            if glow < 0.02:
                continue
            
            # Use the new asset!
            alpha = int(glow * 255)
            # Create a tinted/glow version by setting image alpha
            # (We keep the polygon logic below for easy rollback)
            # pts = [(0, wh), (ww, wh), (ww, wh // 3), (ww // 2, 0), (0, wh // 3)]
            # tmp = pygame.Surface((ww, wh), pygame.SRCALPHA)
            # pygame.draw.polygon(tmp, (*col, int(glow * 200)), pts)
            
            # Draw the PNG asset with pulsing alpha
            asset = self.side_window_surf.copy()
            asset.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(asset, (wx - ww // 2, wy - wh))

    def _draw_spectrum_bars(self, surf, spectrum: np.ndarray):
        """Symmetric spectrum bars resting on a black bar at the bottom with a noise gate."""
        # Noise Gate: Ignore very low-level background hiss/noise
        NOISE_THRESHOLD = 0.08
        # Apply the gate to our spectrum array (vectorized for performance)
        spectrum = np.where(spectrum < NOISE_THRESHOLD, 0.0, spectrum)

        # Draw the 10-pixel black bar across the bottom
        pygame.draw.rect(surf, (0, 0, 0), pygame.Rect(0, self.H - 10, self.W, 10))

        n     = len(spectrum)
        if not hasattr(self, 'bar_peaks') or len(self.bar_peaks) != n:
            self.bar_peaks = [0.0] * n

        bar_w = self.W // (n * 2 + 4)
        max_h = 160
        cx    = self.W // 2
        base_y = self.H - 10

        # Pass 1: Draw the wide, darker bloomy "glow" behind the bars
        for i, val in enumerate(spectrum):
            h    = int(val * max_h)
            t    = i / n
            base_col  = lerp_colour((0, 200, 255), (200, 0, 255), t)
            glow_col = (base_col[0]//3, base_col[1]//3, base_col[2]//3)

            x_r = cx + i * (bar_w + 2) + 4
            x_l = cx - (i + 1) * (bar_w + 2) - 4
            
            if h > 0:
                pygame.draw.rect(surf, glow_col, pygame.Rect(x_r - 2, base_y - h, bar_w + 4, h))
                pygame.draw.rect(surf, glow_col, pygame.Rect(x_l - 2, base_y - h, bar_w + 4, h))

        # Pass 2: Draw the bright core and the falling peak cap
        for i, val in enumerate(spectrum):
            h    = int(val * max_h)
            
            # Update peak hold tracking
            if h >= self.bar_peaks[i]:
                self.bar_peaks[i] = h
            else:
                self.bar_peaks[i] = max(0, self.bar_peaks[i] - 1.5) # Gravity pulling caps down
                
            peak_h = int(self.bar_peaks[i])

            t    = i / n
            base_col  = lerp_colour((0, 255, 255), (255, 0, 255), t)
            # Energy mapping: high intensity bars push towards pure white-hot
            intensity = min(1.0, val * 1.5)
            hot_col = lerp_colour(base_col, (255, 255, 255), intensity)

            x_r = cx + i * (bar_w + 2) + 4
            x_l = cx - (i + 1) * (bar_w + 2) - 4
            
            # Bright Core
            if h > 0:
                pygame.draw.rect(surf, hot_col, pygame.Rect(x_r, base_y - h, bar_w, h))
                pygame.draw.rect(surf, hot_col, pygame.Rect(x_l, base_y - h, bar_w, h))
            
            # Floating Peak Cap
            if peak_h > 0:
                cap_col = lerp_colour(base_col, (255, 255, 255), 0.8)
                pygame.draw.rect(surf, cap_col, pygame.Rect(x_r, base_y - peak_h - 2, bar_w, 2))
                pygame.draw.rect(surf, cap_col, pygame.Rect(x_l, base_y - peak_h - 2, bar_w, 2))


    def _create_bolt_path(self, surface, start_pos, end_pos, displacement, detail_threshold):
        """Recursively draws a jagged lightning bolt on a transparent surface."""
        if displacement < detail_threshold:
            # Draw core
            pygame.draw.line(surface, (230, 245, 255, 255), start_pos, end_pos, width=2)
            # Draw slight glow
            pygame.draw.line(surface, (180, 210, 255, 80), start_pos, end_pos, width=6)
            return

        mid_x = (start_pos[0] + end_pos[0]) / 2 + random.uniform(-displacement, displacement)
        mid_y = (start_pos[1] + end_pos[1]) / 2 + random.uniform(-displacement, displacement)
        new_mid = (mid_x, mid_y)

        self._create_bolt_path(surface, start_pos, new_mid, displacement / 2, detail_threshold)
        self._create_bolt_path(surface, new_mid, end_pos, displacement / 2, detail_threshold)

        if random.random() < 0.2: # 20% branch chance
            branch_x = new_mid[0] + random.uniform(-displacement * 3, displacement * 3)
            branch_y = new_mid[1] + random.uniform(0, displacement * 4)
            self._create_bolt_path(surface, new_mid, (branch_x, branch_y), displacement / 2.5, detail_threshold)

    def _trigger_bolt(self):
        """Generate a random jagged bolt in one of the open sky areas."""
        self.bolt_surf.fill((0, 0, 0, 0))
        self.bolt_alpha = 255
        
        # Left or Right side of Cathedral
        if random.choice([True, False]):
            start_x = random.randint(100, self.W // 2 - 400)
            end_x   = start_x + random.randint(-150, 150)
        else:
            start_x = random.randint(self.W // 2 + 400, self.W - 100)
            end_x   = start_x + random.randint(-150, 150)
            
        start_pos = (start_x, 0)
        end_pos   = (end_x, self.H // 2 + random.randint(50, 250)) # Strike down
        
        self._create_bolt_path(self.bolt_surf, start_pos, end_pos, 80, 3)
        self._trigger_lightning() # Also flash the screen

    def _trigger_lightning(self):
        # Reduced screen flash intensity since the cloud overlay is doing the heavy lifting now
        self.flash_alpha  = random.randint(60, 130)
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

    def _draw_fog(self, surf, rms: float):
        """Draw a slowly drifting fog layer at the horizon/ground level."""
        # Drifts with a slight pulse in speed based on audio energy
        drift_speed = 0.8 + rms * 2.0
        self.fog_x = (self.fog_x + drift_speed) % self.fog_w
        
        y_pos = self.church_base_y  # Spans exactly from here to bottom (1080)
        
        # Tile twice for seamless wrapping
        surf.blit(self.fog_surf, (-self.fog_x, y_pos))
        surf.blit(self.fog_surf, (self.fog_w - self.fog_x, y_pos))

    def _apply_chromatic_aberration(self, surf):
        """
        Subtle lens color fringing.
        Red channel (+2, +1), Blue channel (-2, -1), Green stationary.
        """
        # 1. Create channel copies using full-frame masks
        # Red channel
        red_buf = surf.copy()
        red_buf.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # Blue channel
        blue_buf = surf.copy()
        blue_buf.fill((0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        
        # 2. Convert original surf to just the Green channel
        surf.fill((0, 255, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # 3. Recombine with offsets
        surf.blit(red_buf,  (2, 1),   special_flags=pygame.BLEND_RGBA_ADD)
        surf.blit(blue_buf, (-2, -1), special_flags=pygame.BLEND_RGBA_ADD)

    # ------------------------------------------------------------------
    # Main render frame
    # ------------------------------------------------------------------
    def render_frame(self, pos_seconds: float, hide_preview: bool = False):
        frame_idx = self.analyzer.get_frame_index(pos_seconds)
        spectrum  = self.analyzer.get_spectrum(frame_idx, n_bands=48)
        bass, mid, treble = self.analyzer.get_bass_mid_treble(frame_idx)
        rms       = self.analyzer.get_rms(frame_idx)
        is_beat   = self.analyzer.is_beat(frame_idx)
        onset     = self.analyzer.get_onset_strength(frame_idx)

        # Scheduled Lightning Bolts
        if pos_seconds >= self.next_bolt_time:
            self._trigger_bolt()
            self.next_bolt_time = pos_seconds + random.uniform(15, 20)

        # All drawing happens on the full-res canvas
        surf = self.canvas

        # --- 1. Sky ---
        self._draw_sky(surf, rms)

        # --- 2. Ground ---
        self._draw_ground(surf)

        # --- 3. Light spill (behind silhouette) ---
        self._draw_light_spill(surf, bass, spectrum)

        # --- 4. Cathedral silhouette ---
        surf.blit(self.cathedral_surf, (0, 0))

        # --- 8. Puddles (Now drawn before fog so fog masks them) ---
        if is_beat:
            for p in random.sample(self.puddles, k=random.randint(1, 3)):
                p.trigger_ripple()
        for p in self.puddles:
            p.update()
            # Puddles reflect window light — tint between dark blue and cyan based on bass
            beat_col = lerp_colour((20, 40, 80), (0, 160, 220), min(bass * 1.5, 1.0))
            p.draw(surf, beat_col, rms)

        # --- 4a. Fog (mask bottom edge of silhouette and puddles) ---
        self._draw_fog(surf, rms)

        # --- 5. Rose window ---
        self._draw_rose_window(surf, spectrum, bass)

        # --- 6. Side windows ---
        self._draw_side_windows(surf, mid, treble)

        # --- 7. Rain ---
        avg_energy = float(spectrum.mean())
        tint_col   = lerp_colour((100, 120, 160),
                                  WINDOW_COLOURS[int(avg_energy * 5)],
                                  min(avg_energy * 1.5, 0.5))
        self._draw_rain(surf, rms, tint_col)

        # Spectrum bars
        self._draw_spectrum_bars(surf, spectrum)

        # Lightning flash
        if onset > 0.85 and random.random() < 0.25:
            self._trigger_lightning()
        self._draw_flash(surf)

        # Apply Chromatic Aberration as the final post-processing step
        self._apply_chromatic_aberration(surf)

        # Scale full canvas down to the preview window
        if not hide_preview:
            preview = pygame.transform.scale(self.canvas, (self.PW, self.PH))
            self.screen.blit(preview, (0, 0))
        else:
            self.screen.fill((10, 6, 18))
            msg = self.font_brand.render("Processing Background Video... Please Wait.", True, (160, 120, 220))
            self.screen.blit(msg, ((self.PW - msg.get_width()) // 2, self.PH // 2))

        pygame.display.flip()

        # Return the full-res canvas for the recorder
        return self.canvas

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

        recording_frame_count = 0
        target_duration = self.analyzer.duration
        user_stopped = False
        hide_preview = False
        last_valid_rt_pos = 0.0

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

            if recorder:
                # Fetch music position (returns None if STOP button was clicked)
                rt_pos = get_pos()
                
                # If audio stopped but we haven't reached the end of the video yet
                if rt_pos is None and not user_stopped:
                    user_stopped = True
                    hide_preview = True
                    # Clamp the catch-up duration so it never renders past the actual end of the song
                    target_duration = min(last_valid_rt_pos, self.analyzer.duration)
                    print(f"[Visualizer] User stopped playback at {target_duration:.2f}s. Catching up...")

                if rt_pos is not None:
                    last_valid_rt_pos = rt_pos
                    # Automatically hide preview and fast-forward if real-time audio is done
                    if rt_pos >= self.analyzer.duration and not hide_preview:
                        hide_preview = True
                        print("[Visualizer] Audio finished playing. Finalizing remaining frames...")
                
                # Use frame-based position for sync
                pos = recording_frame_count / 60.0
                recording_frame_count += 1
                
                # Report progress back to UI
                if recording_frame_count % 30 == 0:
                    prefix = "🎬 Finalizing" if not user_stopped else "🛑 Saving"
                    pct = (pos / max(0.1, target_duration)) * 100
                    status_msg = f"{prefix}: {pos:.1f}s / {target_duration:.1f}s ({pct:.0f}%)"
                    if self.status_callback:
                        self.status_callback(status_msg)
            else:
                # Real-time preview mode
                pos = get_pos()

            # Exit when reach target (either end of song or where user hit stop)
            if pos is not None and pos >= target_duration:
                self.running = False
                break

            canvas = self.render_frame(pos, hide_preview=hide_preview)

            if recorder:
                recorder.write_frame(canvas)  # Always records at full 1920x1080

            # Only cap frame rate if NOT recording (encoding might be slower)
            if not recorder:
                self.clock.tick(60)
            else:
                # Just yield to OS slightly but don't hard-cap
                pygame.time.delay(1)

        if recorder:
            recorder.stop()

        pygame.quit()
