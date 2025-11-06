"""ドラムループ+スイープのリアルタイム再生"""
import subprocess
import numpy as np
from scipy.io import wavfile
from audio_generator import AudioGenerator
import tempfile
import os


def load_and_loop_wav(file_path: str, total_duration: float, sample_rate: int) -> np.ndarray:
    """WAVファイルを読み込んでループ"""
    sr, audio = wavfile.read(file_path)

    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0
    elif audio.dtype == np.float32 or audio.dtype == np.float64:
        audio = audio.astype(np.float32)
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

    if sr != sample_rate:
        ratio = sample_rate / sr
        new_length = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_length)
        audio = np.interp(indices, np.arange(len(audio)), audio)

    total_samples = int(sample_rate * total_duration)
    loop_length = len(audio)
    n_repeats = int(np.ceil(total_samples / loop_length))
    looped = np.tile(audio, n_repeats)
    looped = looped[:total_samples]

    return looped.astype(np.float32)


def play_audio_realtime(audio_data, sample_rate):
    """paplayを使用してリアルタイム再生"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        audio_int16 = np.int16(audio_data * 32767)
        wavfile.write(tmp_path, sample_rate, audio_int16)

        result = subprocess.run(
            ['paplay', tmp_path],
            capture_output=True,
            text=True
        )

        return result.returncode == 0

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    """メイン関数"""
    print("=== ドラムループ + スイープ リアルタイム再生 ===")
    print()

    generator = AudioGenerator(sample_rate=44100)
    duration = 20.0

    # ドラムループを読み込み
    print("ドラムループを読み込み中...")
    drum_track = load_and_loop_wav("edm_drum_loop19.wav", duration, generator.sample_rate)
    drum_track = drum_track * 0.2
    print("  完了")

    # 100Hzの三角波トーン
    print("100Hz 三角波トーンを生成中...")
    track1 = generator.generate_tone(
        frequency=100,
        duration=duration,
        wave_type="triangle",
        volume=0.5
    )
    print("  完了")

    # 400-800Hzの三角波スイープ
    print("400-800Hz 三角波スイープを生成中...")
    track2 = generator.generate_sweep(
        sweep_start=400,
        sweep_end=800,
        sweep_period=5.0,
        duration=duration,
        wave_type="triangle",
        volume=0.5
    )
    print("  完了")

    # ミックス
    print()
    print("トラックをミックス中...")
    mixed_audio = AudioGenerator.mix_tracks([drum_track, track1, track2])
    print("  完了")

    # リアルタイム再生
    print()
    print("リアルタイム再生を開始します...")
    print("（再生中... 20秒）")

    success = play_audio_realtime(mixed_audio, generator.sample_rate)

    if success:
        print()
        print("再生完了！")
    else:
        print()
        print("再生に失敗しました")


if __name__ == "__main__":
    main()
