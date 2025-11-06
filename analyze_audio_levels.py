"""音声ファイルのレベル分析"""
import numpy as np
from scipy.io import wavfile


def calculate_rms(audio):
    """RMS（実効値）を計算"""
    return np.sqrt(np.mean(audio ** 2))


def calculate_peak(audio):
    """ピーク振幅を計算"""
    return np.max(np.abs(audio))


def analyze_wav_file(file_path):
    """WAVファイルの音量を分析"""
    print(f"\n=== {file_path} ===")

    # WAVファイルを読み込み
    sr, audio = wavfile.read(file_path)

    # モノラルに変換（ステレオの場合）
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    # float32に変換
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0

    # 各種指標を計算
    rms = calculate_rms(audio)
    peak = calculate_peak(audio)
    rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf
    peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

    print(f"サンプリングレート: {sr} Hz")
    print(f"サンプル数: {len(audio)}")
    print(f"再生時間: {len(audio) / sr:.2f} 秒")
    print(f"RMS (実効値): {rms:.6f}")
    print(f"RMS (dB): {rms_db:.2f} dB")
    print(f"ピーク振幅: {peak:.6f}")
    print(f"ピーク (dB): {peak_db:.2f} dB")

    return rms, peak


def main():
    """メイン関数"""
    print("=== 音声レベル分析 ===")

    # ドラムループを分析
    drum_rms, drum_peak = analyze_wav_file("edm_drum_loop19.wav")

    # スイープを分析
    sweep_rms, sweep_peak = analyze_wav_file("test_sweep_only.wav")

    # 比較
    print("\n=== 比較 ===")
    print(f"ドラムループのRMS: {drum_rms:.6f}")
    print(f"スイープのRMS: {sweep_rms:.6f}")
    print(f"RMS比率: ドラム/スイープ = {drum_rms/sweep_rms:.2f}倍")
    print()
    print("→ ドラムがスイープの{:.0f}倍の音量です".format(drum_rms/sweep_rms))
    print()
    print("【推奨】")
    print(f"スイープとバランスを取るには、ドラムの音量を {sweep_rms/drum_rms:.3f} 倍（約{sweep_rms/drum_rms*100:.1f}%）にする")
    print(f"または、スイープの音量を {drum_rms/sweep_rms:.3f} 倍（約{drum_rms/sweep_rms*100:.0f}%）にする")


if __name__ == "__main__":
    main()
