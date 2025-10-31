"""音声生成モジュール"""
import numpy as np
from scipy import signal


class AudioGenerator:
    """音声生成クラス"""

    def __init__(self, sample_rate: int = 44100):
        """
        初期化

        Args:
            sample_rate: サンプリングレート（Hz）
        """
        self.sample_rate = sample_rate

    def generate_tone(
        self,
        frequency: int,
        duration: float,
        wave_type: str = "triangle",
        volume: float = 0.7
    ) -> np.ndarray:
        """
        トーン（単一周波数の音）を生成

        Args:
            frequency: 周波数（Hz）
            duration: 再生時間（秒）
            wave_type: 波形タイプ（"triangle", "sine", "square"）
            volume: 音量（0.0-1.0）

        Returns:
            生成された音声データ（numpy配列）
        """
        # サンプル数を計算
        n_samples = int(self.sample_rate * duration)

        # 時間軸を生成
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 波形を生成
        if wave_type == "sine":
            # 正弦波
            audio = np.sin(2 * np.pi * frequency * t)
        elif wave_type == "square":
            # 矩形波
            audio = signal.square(2 * np.pi * frequency * t)
        elif wave_type == "triangle":
            # 三角波
            audio = signal.sawtooth(2 * np.pi * frequency * t, width=0.5)
        else:
            raise ValueError(f"Unsupported wave type: {wave_type}")

        # 音量を調整
        audio = audio * volume

        return audio.astype(np.float32)

    def generate_sweep(
        self,
        sweep_start: int,
        sweep_end: int,
        sweep_period: float,
        duration: float,
        wave_type: str = "triangle",
        volume: float = 0.7
    ) -> np.ndarray:
        """
        スイープ（周波数を変化させる音）を生成

        Args:
            sweep_start: 開始周波数（Hz）
            sweep_end: 終了周波数（Hz）
            sweep_period: スイープ周期（秒）
            duration: 再生時間（秒）
            wave_type: 波形タイプ（"triangle", "sine", "square"）
            volume: 音量（0.0-1.0）

        Returns:
            生成された音声データ（numpy配列）
        """
        # サンプル数を計算
        n_samples = int(self.sample_rate * duration)

        # 時間軸を生成
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # スイープの繰り返し回数を計算
        n_sweeps = duration / sweep_period

        # スイープの周波数変化を計算（滑らかに繰り返し）
        sweep_phase = (t % sweep_period) / sweep_period  # 0-1の範囲で繰り返し
        # 正弦波的に0->1->0と滑らかに変化（開始と終了で変化率が0になる）
        sweep_phase = (1 - np.cos(2 * np.pi * sweep_phase)) / 2
        frequency = sweep_start + (sweep_end - sweep_start) * sweep_phase

        # 位相を計算
        phase = 2 * np.pi * np.cumsum(frequency) / self.sample_rate

        # 波形を生成
        if wave_type == "sine":
            audio = np.sin(phase)
        elif wave_type == "square":
            audio = signal.square(phase)
        elif wave_type == "triangle":
            audio = signal.sawtooth(phase, width=0.5)
        else:
            raise ValueError(f"Unsupported wave type: {wave_type}")

        # 音量を調整
        audio = audio * volume

        return audio.astype(np.float32)

    @staticmethod
    def mix_tracks(tracks: list[np.ndarray]) -> np.ndarray:
        """
        複数のトラックをミックス（重ね合わせ）

        Args:
            tracks: ミックスするトラックのリスト

        Returns:
            ミックスされた音声データ
        """
        if not tracks:
            raise ValueError("No tracks to mix")

        # 最大長を取得
        max_length = max(len(track) for track in tracks)

        # すべてのトラックを最大長に合わせてゼロパディング
        padded_tracks = []
        for track in tracks:
            if len(track) < max_length:
                padded = np.pad(track, (0, max_length - len(track)), mode='constant')
                padded_tracks.append(padded)
            else:
                padded_tracks.append(track)

        # トラックを重ね合わせ
        mixed = np.sum(padded_tracks, axis=0)

        # クリッピング防止のため、最大振幅で正規化
        max_amplitude = np.max(np.abs(mixed))
        if max_amplitude > 1.0:
            mixed = mixed / max_amplitude

        return mixed.astype(np.float32)
