"""
Video recorder: pipes pygame frames into FFmpeg to produce an MP4.
Uses a background thread so it never blocks the render loop.
"""
import subprocess
import threading
import queue
import os
import numpy as np


class VideoRecorder:
    def __init__(self, output_path: str, width: int, height: int,
                 fps: int = 60, audio_path: str = None):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.audio_path = audio_path
        self._proc = None
        self._queue = queue.Queue(maxsize=300)  # Buffer up to 5 seconds of frames
        self._thread = None
        self._running = False

    def start(self):
        """Open FFmpeg pipe and start the writer thread."""
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "rgb24",
            "-r", str(self.fps),
            "-i", "-",   # stdin pipe for video frames
        ]

        if self.audio_path:
            cmd += ["-i", self.audio_path, "-shortest"]

        cmd += [
            "-vcodec", "libx264",
            "-preset", "fast",
            "-crf", "18",         # High quality
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            self.output_path
        ]

        print(f"[Recorder] Starting FFmpeg → {self.output_path}")
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL)
        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def _writer_loop(self):
        """Background thread that drains the queue and writes to FFmpeg stdin."""
        while self._running or not self._queue.empty():
            try:
                frame = self._queue.get(timeout=0.1)
                if frame is None:
                    break
                self._proc.stdin.write(frame.tobytes())
            except queue.Empty:
                continue
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        self._proc.wait()
        print(f"[Recorder] Encode complete → {self.output_path}")

    def write_frame(self, surface):
        """
        Called each frame with the pygame Surface.
        Converts to numpy RGB and queues it for the writer thread.
        """
        import pygame
        if not self._running:
            return
        try:
            raw = pygame.surfarray.array3d(surface)
            # pygame uses (x, y) but FFmpeg wants (y, x) = (H, W, 3)
            frame = np.transpose(raw, (1, 0, 2))
            # Block if queue is full to ensure NO frames are dropped
            self._queue.put(frame, block=True)
        except Exception as e:
            print(f"[Recorder] Error queuing frame: {e}")

    def stop(self):
        """Signal writer thread to finish and wait for FFmpeg to finalize."""
        self._running = False
        self._queue.put(None)  # Sentinel
        if self._thread:
            self._thread.join(timeout=30)
        print("[Recorder] Stopped.")

    def discard(self):
        """Stop recording and delete the output file."""
        self.stop()
        if os.path.exists(self.output_path):
            os.remove(self.output_path)
            print(f"[Recorder] Discarded: {self.output_path}")
