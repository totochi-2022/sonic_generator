"""利用可能な音声デバイスをリスト表示"""
import sounddevice as sd

print("=== 利用可能な音声デバイス ===")
print()
print(sd.query_devices())
print()
print(f"デフォルト入力デバイス: {sd.default.device[0]}")
print(f"デフォルト出力デバイス: {sd.default.device[1]}")
