"""
Launcher UI — tkinter control panel for AVizualizer.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time
import pygame


ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
LOGO_PATH  = os.path.join(ASSETS_DIR, "FilledCrossBGF.png")

BG        = "#0d0818"
BG_PANEL  = "#16112a"
ACCENT    = "#7a3fe4"
ACCENT2   = "#00c8ff"
TEXT      = "#e8e0ff"
TEXT_DIM  = "#7a6a99"


class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AVizualizer — Modern Christian Rock Music")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.audio_path  = tk.StringVar(value="")
        self.resolution  = tk.StringVar(value="1920x1080")
        self.is_running  = False
        self._viz_thread = None
        self._recorder   = None

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = self.root

        # Title bar
        title_frame = tk.Frame(root, bg=BG, pady=16)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="⛪  AVizualizer",
                 bg=BG, fg=ACCENT2, font=("Georgia", 22, "bold")).pack()
        tk.Label(title_frame, text="Modern Christian Rock Music — Cathedral in the Storm",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 10)).pack()

        sep = tk.Frame(root, bg=ACCENT, height=1)
        sep.pack(fill=tk.X, padx=20)

        # Main panel
        panel = tk.Frame(root, bg=BG_PANEL, padx=30, pady=20)
        panel.pack(fill=tk.BOTH, padx=20, pady=16)

        # Audio file row
        tk.Label(panel, text="Audio File", bg=BG_PANEL, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=(0, 4))

        file_row = tk.Frame(panel, bg=BG_PANEL)
        file_row.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.file_lbl = tk.Label(file_row, textvariable=self.audio_path,
                                  bg=BG_PANEL, fg=TEXT, font=("Segoe UI", 10),
                                  width=42, anchor="w", relief="flat",
                                  bd=1, padx=6)
        self.file_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        tk.Button(file_row, text="📂  Browse", bg=ACCENT, fg=TEXT,
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  command=self._browse_audio, padx=10).pack(side=tk.RIGHT, padx=(8, 0))

        # Resolution
        tk.Label(panel, text="Output Resolution", bg=BG_PANEL, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=(14, 4))

        res_combo = ttk.Combobox(panel, textvariable=self.resolution, state="readonly",
                                  values=["1920x1080 (YouTube HD)", "1280x720 (Preview)"],
                                  font=("Segoe UI", 10), width=30)
        res_combo.grid(row=3, column=0, sticky="w")
        res_combo.current(0)

        # Status
        self.status_var = tk.StringVar(value="Ready. Load an audio file to begin.")
        tk.Label(panel, textvariable=self.status_var,
                 bg=BG_PANEL, fg=ACCENT2, font=("Segoe UI", 9, "italic"),
                 wraplength=400, justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(14, 0))

        sep2 = tk.Frame(root, bg="#2a1f44", height=1)
        sep2.pack(fill=tk.X, padx=20)

        # Control buttons
        btn_frame = tk.Frame(root, bg=BG, pady=16)
        btn_frame.pack()

        self.start_btn = tk.Button(
            btn_frame, text="▶  START  Recording",
            bg="#1db954", fg="white",
            font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2",
            padx=24, pady=10, command=self._on_start)
        self.start_btn.pack(side=tk.LEFT, padx=8)

        self.stop_btn = tk.Button(
            btn_frame, text="⏹  STOP",
            bg="#c0392b", fg="white",
            font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2",
            padx=24, pady=10, state="disabled", command=self._on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=8)

        tk.Button(btn_frame, text="📁  Output Folder",
                  bg=BG_PANEL, fg=TEXT_DIM,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=10, command=self._open_output).pack(side=tk.LEFT, padx=8)

        # Footer
        tk.Label(root, text="Press ESC inside the visualizer window to stop at any time.",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 8)).pack(pady=(0, 10))

    # ------------------------------------------------------------------
    def _browse_audio(self):
        path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio Files", "*.mp3 *.wav *.flac *.ogg"), ("All Files", "*.*")]
        )
        if path:
            self.audio_path.set(path)
            fname = os.path.basename(path)
            self.status_var.set(f"Loaded: {fname} — Ready to start!")

    def _open_output(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.startfile(OUTPUT_DIR)

    # ------------------------------------------------------------------
    def _on_start(self):
        if not self.audio_path.get():
            messagebox.showwarning("No Audio", "Please select an audio file first.")
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("🔄 Analyzing audio — please wait...")
        self.is_running = True

        self._viz_thread = threading.Thread(target=self._run_visualizer, daemon=True)
        self._viz_thread.start()

    def _on_stop(self):
        """User manually hits STOP — confirm keep or discard."""
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

        # The visualizer loop monitors self.is_running and will call recorder.stop()
        # We give a brief moment then ask
        self.root.after(1500, self._prompt_keep_discard)

    def _prompt_keep_discard(self):
        if not hasattr(self, "_last_output") or not self._last_output:
            return
        path = self._last_output
        if not os.path.exists(path):
            return
        keep = messagebox.askyesno(
            "Keep Recording?",
            f"Do you want to keep the recording?\n\n{os.path.basename(path)}"
        )
        if keep:
            self.status_var.set(f"✅ Saved: {path}")
            messagebox.showinfo("Saved!", f"Video saved to:\n{path}")
        else:
            os.remove(path)
            self.status_var.set("🗑️ Recording discarded.")

    # ------------------------------------------------------------------
    def _run_visualizer(self):
        """Runs in a background thread."""
        try:
            from engine.audio_analyzer import AudioAnalyzer
            from engine.recorder       import VideoRecorder
            from visualizer.cathedral_storm import CathedralStormVisualizer

            audio_file = self.audio_path.get()
            self.root.after(0, lambda: self.status_var.set("📊 Analyzing spectrum..."))

            analyzer = AudioAnalyzer(audio_file)

            # Output file
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            base = os.path.splitext(os.path.basename(audio_file))[0]
            ts   = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(OUTPUT_DIR, f"{base}_{ts}.mp4")
            self._last_output = out_path

            # Resolution
            res_str = self.resolution.get().split()[0]
            W, H    = map(int, res_str.split("x"))

            recorder = VideoRecorder(out_path, W, H, fps=60, audio_path=audio_file)
            recorder.start()
            self._recorder = recorder

            self.root.after(0, lambda: self.status_var.set("🎬 Recording! Press ESC or STOP to finish."))

            # Pygame playback sync
            pygame.mixer.init(frequency=44100, channels=2, buffer=1024)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            _start_time = time.time()

            def get_pos():
                # If launcher stopped us, signal visualizer to quit
                if not self.is_running:
                    return None
                return time.time() - _start_time

            viz = CathedralStormVisualizer(analyzer, LOGO_PATH)
            viz.run(audio_start_fn=lambda: get_pos, recorder=recorder)

            # After loop ends (song finished or ESC)
            pygame.mixer.music.stop()
            pygame.mixer.quit()

            self.root.after(0, self._on_viz_finished)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status_var.set(f"❌ Error: {e}"))
            self.root.after(0, lambda: self.start_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_btn.config(state="disabled"))

    def _on_viz_finished(self):
        """Called from main thread after visualizer loop exits normally (song ended)."""
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

        if hasattr(self, "_last_output") and os.path.exists(self._last_output):
            self.status_var.set(f"✅ Done! Video saved to: {self._last_output}")
            messagebox.showinfo("Export Complete",
                f"🎉 Your video is ready!\n\n{self._last_output}")
        else:
            self.status_var.set("Done.")

    # ------------------------------------------------------------------
    def run(self):
        self.root.mainloop()
