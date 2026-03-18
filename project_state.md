# Audio Visualizer Project: Current State & Next Steps

## 1. Current System Architecture
We are building a heavy metal/djent audio visualizer in Python (Pygame). The system is driven by a real-time 48-band FFT and features the following working components:
* **Electric Spectrum Bars:** Vectorized noise gate (`np.where` below 5% threshold) with gravity-based peak caps and heat-map color mapping.
* **Atmospherics:** RMS-driven rain speed and fog density, plus recursive/onset-triggered lightning bolts.
* **Dual-Layer Center Window:**
    * **Layer 1 (Main Glass):** Ambient "breathing" mapped to smoothed RMS with a floor cutoff so it only swells on heavy chords.
    * **Layer 2 (Blue Halo):** A kinetic strobe triggered by transient spikes in the high-mid frequencies (`.max()` of bands 30-40) to catch the kick drum. It uses a strict state machine (Attack -> 0.08s Hold -> Release -> 0.12s Cooldown).

## 2. The Current Problem
The Layer 2 Blue Halo works perfectly in quiet intro sections. However, when the heavy "Wall of Sound" drop hits, the high-mid frequencies become saturated by distorted guitars and cymbals. The static transient threshold gets overwhelmed, causing the strobe to lock "on" or pulse mushily instead of snapping violently.

## 3. Next Steps: Dual-State Dynamic Threshold
We need to implement an "Envelope Follower" macro-state machine to make the halo context-aware. 

**Task:** Update the `_draw_rose_window` function with the following logic:
1.  **Macro 'Song State':** Track the overall `rms`. 
    * If `rms > 0.75`, enter **HEAVY STATE**. 
    * If `rms < 0.65`, enter **QUIET STATE**.
2.  **Dynamic Threshold Swap:**
    * In **QUIET STATE**, the halo's high-mid trigger threshold remains at `0.65`.
    * In **HEAVY STATE**, the trigger threshold must shift to `0.90` so it ignores the guitars and only flashes on the sharpest kick drum peaks.
3.  **Dynamic Color Shift:**
    * In **QUIET STATE**, render the halo in its original Cyan.
    * In **HEAVY STATE**, swap the halo color to an aggressive Red or Magenta.
4.  **Preservation Rule:** Do absolutely nothing to alter the micro-timers (0.08s Hold, 0.12s Cooldown). Only alter the threshold that triggers the initial Attack state.
