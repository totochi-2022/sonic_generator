"""バスドラム（キック）音の生成"""
import numpy as np
from scipy.io import wavfile


def generate_kick_drum(sample_rate=44100):
    """
    バスドラム（キック）音を合成生成

    Args:
        sample_rate: サンプリングレート

    Returns:
        バスドラムの音声データ
    """
    duration = 0.5  # 0.5秒
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # 周波数エンベロープ（高い周波数から低い周波数へ急速に下降）
    start_freq = 150  # 開始周波数
    end_freq = 40     # 終了周波数（バスドラムの基本周波数）
    freq_decay = 0.05 # 周波数減衰時間

    # 指数関数的に周波数を減衰
    frequency = end_freq + (start_freq - end_freq) * np.exp(-t / freq_decay)

    # 位相を計算
    phase = 2 * np.pi * np.cumsum(frequency) / sample_rate

    # サイン波を生成
    kick = np.sin(phase)

    # 振幅エンベロープ（急激な減衰）
    amp_decay = 0.3  # 振幅減衰時間
    envelope = np.exp(-t / amp_decay)

    # エンベロープを適用
    kick = kick * envelope

    # クリック音を追加（アタック感を出すため）
    click_duration = 0.01
    click_samples = int(sample_rate * click_duration)
    click = np.random.randn(click_samples) * 0.3
    click_env = np.exp(-np.linspace(0, 10, click_samples))
    click = click * click_env

    # クリックをミックス
    kick[:click_samples] += click

    # 音量調整
    kick = kick * 0.8

    # 正規化
    max_val = np.max(np.abs(kick))
    if max_val > 0:
        kick = kick / max_val

    return kick.astype(np.float32)


def main():
    """メイン関数"""
    print("=== バスドラム音生成 ===")
    print()

    sample_rate = 44100
    print("バスドラム音を生成中...")
    kick = generate_kick_drum(sample_rate)

    print(f"生成完了: {len(kick)} サンプル")
    print()

    # WAVファイルとして保存
    output_file = "kick_drum.wav"
    print(f"WAVファイルに保存中: {output_file}")

    # float32からint16に変換
    kick_int16 = np.int16(kick * 32767)
    wavfile.write(output_file, sample_rate, kick_int16)

    print("保存完了！")
    print()
    print(f"生成されたファイル: {output_file}")
    print("合成バスドラム音（キック）が保存されました。")


if __name__ == "__main__":
    main()
