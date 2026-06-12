"""音声生成モジュール

ステレオ2ch + うなり(beat)方式に対応。
- mono運用: delta_f=0 → L=R(同一波形)
- beat運用: L=fc−Δf/2, R=fc+Δf/2 → 左右の周波数差(うなり)で節を横走査
位相は L/R とも cumsum で積分するため、fc・Δf のどちらが時間変化しても正しく追従する。
"""
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

    def _wave(self, wave_type: str, phase: np.ndarray) -> np.ndarray:
        """位相配列から波形を生成（共通ヘルパー）"""
        if wave_type == "sine":
            return np.sin(phase)
        elif wave_type == "square":
            return signal.square(phase)
        elif wave_type == "triangle":
            return signal.sawtooth(phase, width=0.5)
        raise ValueError(f"Unsupported wave type: {wave_type}")

    def _delta_f_array(
        self,
        t: np.ndarray,
        delta_f: float,
        delta_f_end,
        delta_f_period,
    ) -> np.ndarray:
        """瞬時Δf(t)を返す。delta_f_end/period 未設定なら一定Δf。

        設定時は delta_f <-> delta_f_end を raised-cosine で滑らかに往復
        （fcスイープと同じ形）。符号をまたぐと節が止まり向きが反転する。
        """
        if delta_f_end is None or delta_f_period is None:
            return np.full_like(t, float(delta_f))
        ph = (t % delta_f_period) / delta_f_period
        ph = (1 - np.cos(2 * np.pi * ph)) / 2          # 0->1->0
        return delta_f + (delta_f_end - delta_f) * ph

    def _render_stereo(
        self,
        fc: np.ndarray,
        t: np.ndarray,
        wave_type: str,
        volume: float,
        delta_f: float,
        delta_f_end,
        delta_f_period,
    ) -> np.ndarray:
        """中心周波数fc(t)とΔf(t)から (n,2) のステレオ波形を生成。

        位相は cumsum で積分するので、fc/Δf が時間変化してもうなりが
        位相差として正しく現れる。
        """
        df = self._delta_f_array(t, delta_f, delta_f_end, delta_f_period)   # (n,)
        fL = fc - df / 2.0
        fR = fc + df / 2.0
        phase_L = 2 * np.pi * np.cumsum(fL) / self.sample_rate
        phase_R = 2 * np.pi * np.cumsum(fR) / self.sample_rate
        left = self._wave(wave_type, phase_L)
        right = self._wave(wave_type, phase_R)
        stereo = np.stack([left, right], axis=1) * volume                  # (n,2)
        return stereo.astype(np.float32)

    def generate_tone(
        self,
        frequency: int,
        duration: float,
        wave_type: str = "triangle",
        volume: float = 0.7,
        delta_f: float = 0.0,
        delta_f_end=None,
        delta_f_period=None,
    ) -> np.ndarray:
        """
        トーン（単一中心周波数）をステレオ生成

        Args:
            frequency: 中心周波数（Hz）
            duration: 再生時間（秒）
            wave_type: 波形タイプ（"triangle", "sine", "square"）
            volume: 音量（0.0-1.0）
            delta_f: L/R周波数差[Hz]（一定値 or スイープ開始値、符号付き）
            delta_f_end: 設定時Δfをここまでスイープ
            delta_f_period: Δfスイープ周期[秒]

        Returns:
            生成された音声データ（numpy配列, shape=(n,2)）
        """
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)
        fc = np.full_like(t, float(frequency))
        return self._render_stereo(
            fc, t, wave_type, volume, delta_f, delta_f_end, delta_f_period
        )

    def generate_sweep(
        self,
        sweep_start: int,
        sweep_end: int,
        sweep_period: float,
        duration: float,
        wave_type: str = "triangle",
        volume: float = 0.7,
        delta_f: float = 0.0,
        delta_f_end=None,
        delta_f_period=None,
    ) -> np.ndarray:
        """
        スイープ（中心周波数を変化させる音）をステレオ生成

        Args:
            sweep_start: 開始周波数（Hz）
            sweep_end: 終了周波数（Hz）
            sweep_period: スイープ周期（秒）
            duration: 再生時間（秒）
            wave_type: 波形タイプ（"triangle", "sine", "square"）
            volume: 音量（0.0-1.0）
            delta_f: L/R周波数差[Hz]（一定値 or スイープ開始値、符号付き）
            delta_f_end: 設定時Δfをここまでスイープ
            delta_f_period: Δfスイープ周期[秒]（fcのsweep_periodと独立）

        Returns:
            生成された音声データ（numpy配列, shape=(n,2)）
        """
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 中心周波数スイープ（滑らかに繰り返し: 開始と終了で変化率0）
        sweep_phase = (t % sweep_period) / sweep_period
        sweep_phase = (1 - np.cos(2 * np.pi * sweep_phase)) / 2
        fc = sweep_start + (sweep_end - sweep_start) * sweep_phase

        return self._render_stereo(
            fc, t, wave_type, volume, delta_f, delta_f_end, delta_f_period
        )

    @staticmethod
    def mix_tracks(tracks: list[np.ndarray]) -> np.ndarray:
        """
        複数のトラックをミックス（重ね合わせ）

        Args:
            tracks: ミックスするトラックのリスト（各 (n,2) または後方互換の (n,)）

        Returns:
            ミックスされた音声データ（(n,2)）
        """
        if not tracks:
            raise ValueError("No tracks to mix")

        # 最大長を取得
        max_length = max(len(track) for track in tracks)

        # すべてのトラックを2ch化して最大長にゼロパディング
        padded_tracks = []
        for track in tracks:
            if track.ndim == 1:                       # 後方互換: モノラルは2chに複製
                track = np.stack([track, track], axis=1)
            if len(track) < max_length:
                track = np.pad(
                    track, ((0, max_length - len(track)), (0, 0)), mode="constant"
                )
            padded_tracks.append(track)

        # トラックを重ね合わせ
        mixed = np.sum(padded_tracks, axis=0)         # (n,2)

        # クリッピング防止: L/R共通スケールで正規化（別々正規化は左右バランス/うなりを壊す）
        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed = mixed / peak

        return mixed.astype(np.float32)
