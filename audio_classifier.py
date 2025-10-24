# -*- coding: utf-8 -*-
import os, math
import numpy as np
import librosa
from pydub import AudioSegment
from pathlib import Path

def ogg_or_m4a_to_wav(src_path: str, dst_path: str, target_sr: int = 32000):
    audio = AudioSegment.from_file(src_path)
    audio = audio.set_channels(1).set_frame_rate(target_sr)
    audio.export(dst_path, format="wav")
    return dst_path

class HeuristicFartClassifier:
    def __init__(self, cfg: dict):
        self.lowfreq_ratio_min = float(cfg.get('HEURISTIC_LOWFREQ_RATIO', 1.35))
        self.rolloff_max = float(cfg.get('HEURISTIC_ROLLOFF_MAX', 1600))
        self.zcr_max = float(cfg.get('HEURISTIC_ZCR_MAX', 0.12))

    def classify(self, wav_path: str):
        y, sr = librosa.load(wav_path, sr=32000, mono=True)
        duration = len(y) / sr
        if duration < 0.5:
            return {"is_fart": False, "score": 0.0, "debug": {"reason": "too_short", "duration": duration}}
        y = librosa.util.normalize(y)

        S = np.abs(np.fft.rfft(y))**2
        freqs = np.fft.rfftfreq(len(y), 1.0/sr)
        def band_energy(fmin, fmax):
            idx = np.where((freqs >= fmin) & (freqs < fmax))[0]
            if len(idx) == 0:
                return 0.0
            return float(S[idx].sum())

        low = band_energy(20, 250)
        mid = band_energy(250, 2000)
        low_ratio = (low + 1e-9) / (mid + 1e-9)

        zcr = float(librosa.feature.zero_crossing_rate(y=y, frame_length=1024, hop_length=512).mean())
        rolloff = float(librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85).mean())

        import math
        p_low = 1 / (1 + math.exp(-6*(low_ratio - self.lowfreq_ratio_min)))
        p_roll = 1 / (1 + math.exp(-0.004*(self.rolloff_max - rolloff)))
        p_zcr = 1 / (1 + math.exp(-50*(self.zcr_max - zcr)))
        score = 0.5*p_low + 0.3*p_zcr + 0.2*p_roll
        is_fart = (score >= 0.55)

        return {
            "is_fart": bool(is_fart),
            "score": float(score),
            "debug": {
                "low_ratio": float(low_ratio),
                "zcr": zcr,
                "rolloff": rolloff,
            }
        }

class FartClassifier:
    def __init__(self, mode: str = "heuristic", cfg: dict = None):
        self.mode = mode or "heuristic"
        self.cfg = cfg or {}
        self.heur = HeuristicFartClassifier(self.cfg)

    def classify(self, wav_path: str):
        return self.heur.classify(wav_path)
