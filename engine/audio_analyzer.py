"""Audio analysis engine — FFT, beat detection, RMS."""
import numpy as np
import librosa


class AudioAnalyzer:
    def __init__(self, filepath: str, fft_size: int = 2048):
        self.filepath = filepath
        self.fft_size = fft_size

        # Load the full audio file once
        print(f"[AudioAnalyzer] Loading: {filepath}")
        self.audio, self.sr = librosa.load(filepath, sr=44100, mono=True)
        self.duration = len(self.audio) / self.sr
        print(f"[AudioAnalyzer] Duration: {self.duration:.2f}s  SR: {self.sr}")

        # Pre-compute short-time Fourier transform
        self.stft = np.abs(librosa.stft(self.audio, n_fft=fft_size, hop_length=512))
        self.n_frames = self.stft.shape[1]

        # Beat tracking
        self.tempo, self.beat_frames = librosa.beat.beat_track(
            y=self.audio, sr=self.sr, hop_length=512
        )
        # librosa may return tempo as a numpy array in newer versions — cast to scalar
        self.tempo = float(np.atleast_1d(self.tempo)[0])

        # RMS energy per frame
        self.rms_frames = librosa.feature.rms(
            y=self.audio, frame_length=fft_size, hop_length=512
        )[0]
        self.rms_max = float(self.rms_frames.max()) or 1.0

        # Onset strength for transient detection
        self.onset_env = librosa.onset.onset_strength(y=self.audio, sr=self.sr, hop_length=512)
        self.onset_max = float(self.onset_env.max()) or 1.0

        print(f"[AudioAnalyzer] Ready. Tempo: {self.tempo:.1f} BPM")

    def get_frame_index(self, playback_pos_seconds: float) -> int:
        """Convert playback position (seconds) to STFT frame index."""
        idx = int(playback_pos_seconds * self.sr / 512)
        return min(idx, self.n_frames - 1)

    def get_spectrum(self, frame_idx: int, n_bands: int = 64) -> np.ndarray:
        """
        Returns `n_bands` frequency magnitude values (0.0–1.0) for the given frame.
        Logarithmically spaced for perceptual accuracy.
        """
        col = self.stft[:, frame_idx]
        # Bin into n_bands log-spaced groups
        freqs = np.logspace(np.log10(20), np.log10(self.sr / 2), n_bands + 1)
        freq_bin = np.fft.rfftfreq(self.fft_size, d=1.0 / self.sr)
        bands = np.zeros(n_bands)
        for i in range(n_bands):
            mask = (freq_bin >= freqs[i]) & (freq_bin < freqs[i + 1])
            if mask.any():
                bands[i] = col[mask].mean()
        # Normalize to 0-1
        peak = bands.max()
        if peak > 0:
            bands = bands / peak
        return bands

    def get_bass_mid_treble(self, frame_idx: int) -> tuple[float, float, float]:
        """Returns normalized (bass, mid, treble) energy for the frame."""
        col = self.stft[:, frame_idx]
        freq_bin = np.fft.rfftfreq(self.fft_size, d=1.0 / self.sr)

        bass   = col[(freq_bin >= 20)   & (freq_bin < 250)].mean()
        mid    = col[(freq_bin >= 250)  & (freq_bin < 3000)].mean()
        treble = col[(freq_bin >= 3000) & (freq_bin < 20000)].mean()

        peak = max(bass, mid, treble, 1e-6)
        return float(bass / peak), float(mid / peak), float(treble / peak)

    def get_rms(self, frame_idx: int) -> float:
        """Normalized RMS energy 0.0–1.0."""
        return float(self.rms_frames[min(frame_idx, len(self.rms_frames) - 1)] / self.rms_max)

    def is_beat(self, frame_idx: int) -> bool:
        """True if this frame coincides with a detected beat."""
        return frame_idx in self.beat_frames

    def get_onset_strength(self, frame_idx: int) -> float:
        """Normalized onset (transient) strength 0.0–1.0."""
        idx = min(frame_idx, len(self.onset_env) - 1)
        return float(self.onset_env[idx] / self.onset_max)
