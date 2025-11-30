"""FastAPIメインアプリケーション"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request
import json
import os
import uuid
from pathlib import Path
from typing import List, Dict
import numpy as np
from scipy.io import wavfile
import threading
from concurrent.futures import ThreadPoolExecutor
import subprocess
import tempfile

from models import Program, Stage, Track, PlaybackStatus
from audio_generator import AudioGenerator

app = FastAPI(title="音波洗浄システム")

# オーディオバックエンド設定（"paplay" or "sounddevice"）
# コマンドライン引数で指定可能（デフォルトはpaplay）
AUDIO_BACKEND = "paplay"

# 静的ファイルとテンプレート
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ディレクトリ設定
PROGRAMS_DIR = Path("programs")
EXPORTS_DIR = Path("exports")
PROGRAMS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# メモリ内プログラム保存（実際のアプリではDBを使用）
programs_db: Dict[str, Program] = {}

# 再生ステータス
playback_status = PlaybackStatus()

# 再生管理
current_playback_process = None
playback_lock = threading.Lock()
is_playing = False
current_program_id = None
skip_to_stage = None

# スレッドプール
executor = ThreadPoolExecutor(max_workers=1)


# ===== オーディオバックエンド =====

def get_audio_backend() -> str:
    """使用するオーディオバックエンドを取得"""
    return AUDIO_BACKEND


# ===== ヘルパー関数 =====

def load_programs_from_disk():
    """ディスクからプログラムを読み込み"""
    for file_path in PROGRAMS_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                program = Program(**data)
                programs_db[program.id] = program
        except Exception as e:
            print(f"プログラム読み込みエラー {file_path}: {e}")


def save_program_to_disk(program: Program):
    """プログラムをディスクに保存"""
    file_path = PROGRAMS_DIR / f"{program.id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(program.model_dump(), f, ensure_ascii=False, indent=2)


def delete_program_from_disk(program_id: str):
    """プログラムをディスクから削除"""
    file_path = PROGRAMS_DIR / f"{program_id}.json"
    if file_path.exists():
        file_path.unlink()


def generate_audio_for_track(track: Track, duration: float, generator: AudioGenerator) -> np.ndarray:
    """トラックの音声データを生成（ステージのdurationを使用）"""
    if track.type == "tone":
        return generator.generate_tone(
            frequency=track.frequency,
            duration=duration,
            wave_type=track.wave_type,
            volume=track.volume
        )
    elif track.type == "sweep":
        return generator.generate_sweep(
            sweep_start=track.sweep_start,
            sweep_end=track.sweep_end,
            sweep_period=track.sweep_period,
            duration=duration,
            wave_type=track.wave_type,
            volume=track.volume
        )
    elif track.type == "wave_file":
        # WAVファイル読み込み処理（後で実装）
        raise NotImplementedError("wave_file type not yet implemented")
    else:
        raise ValueError(f"Unknown track type: {track.type}")


def generate_audio_for_stage(stage: Stage, generator: AudioGenerator) -> np.ndarray:
    """ステージの音声データを生成（有効なトラックのみミックス）"""
    audio_tracks = []
    for track in stage.tracks:
        if track.enabled:  # 有効なトラックのみ処理
            audio_tracks.append(generate_audio_for_track(track, stage.duration, generator))

    if not audio_tracks:
        # 空のステージの場合、ステージの時間分の無音を返す
        return np.zeros(int(generator.sample_rate * stage.duration), dtype=np.float32)

    return AudioGenerator.mix_tracks(audio_tracks)


def stop_current_playback():
    """現在の再生を停止"""
    global current_playback_process, is_playing, playback_status, current_program_id

    backend = get_audio_backend()

    with playback_lock:
        if backend == "paplay":
            # paplayプロセスを停止
            if current_playback_process and current_playback_process.poll() is None:
                try:
                    current_playback_process.terminate()
                    current_playback_process.wait(timeout=2)
                except:
                    try:
                        current_playback_process.kill()
                    except:
                        pass
                current_playback_process = None
        elif backend == "sounddevice":
            # sounddeviceを停止
            if is_playing:
                try:
                    import sounddevice as sd
                    sd.stop()
                except:
                    pass
        is_playing = False
        current_program_id = None
        playback_status.is_playing = False


def stop_current_playback_audio():
    """現在再生中の音声のみ停止（再生ループは継続）"""
    global current_playback_process

    backend = get_audio_backend()

    with playback_lock:
        if backend == "paplay":
            if current_playback_process and current_playback_process.poll() is None:
                try:
                    current_playback_process.terminate()
                    current_playback_process.wait(timeout=1)
                except:
                    try:
                        current_playback_process.kill()
                    except:
                        pass
                current_playback_process = None
        elif backend == "sounddevice":
            try:
                import sounddevice as sd
                sd.stop()
            except:
                pass


def play_audio_realtime(audio_data: np.ndarray, sample_rate: int):
    """リアルタイム再生（バックエンドに応じて切り替え）"""
    global current_playback_process, is_playing

    backend = get_audio_backend()

    if backend == "paplay":
        # paplayを使用（Linux/WSL）
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            audio_int16 = np.int16(audio_data * 32767)
            wavfile.write(tmp_path, sample_rate, audio_int16)

            with playback_lock:
                current_playback_process = subprocess.Popen([
                    'paplay',
                    '--latency-msec=200',
                    tmp_path
                ])
                is_playing = True

            current_playback_process.wait()  # 再生完了を待つ

            with playback_lock:
                if current_playback_process:
                    current_playback_process = None
                is_playing = False
        except:
            with playback_lock:
                is_playing = False
            raise
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    elif backend == "sounddevice":
        # sounddeviceを使用（Windows/macOS）
        import sounddevice as sd

        with playback_lock:
            is_playing = True

        try:
            sd.play(audio_data, sample_rate)
            sd.wait()  # 再生完了を待つ
        finally:
            with playback_lock:
                is_playing = False
    else:
        raise ValueError(f"Unknown audio backend: {backend}")


# ===== ルート =====

@app.on_event("startup")
async def startup_event():
    """起動時にプログラムを読み込み"""
    load_programs_from_disk()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """プログラム一覧ページ"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "programs": list(programs_db.values())
    })


@app.get("/program/{program_id}", response_class=HTMLResponse)
async def program_edit(request: Request, program_id: str):
    """プログラム編集ページ"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    return templates.TemplateResponse("program.html", {
        "request": request,
        "program": programs_db[program_id]
    })


# ===== プログラム管理 API =====

@app.get("/api/programs")
async def get_programs() -> List[Program]:
    """プログラム一覧取得"""
    return list(programs_db.values())


@app.post("/api/programs")
async def create_program(program: Program) -> Program:
    """プログラム作成"""
    program.id = str(uuid.uuid4())
    programs_db[program.id] = program
    save_program_to_disk(program)
    return program


@app.get("/api/programs/{program_id}")
async def get_program(program_id: str) -> Program:
    """プログラム取得"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")
    return programs_db[program_id]


@app.put("/api/programs/{program_id}")
async def update_program(program_id: str, updates: dict) -> Program:
    """プログラム部分更新"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]

    # 部分更新: 渡されたフィールドのみ更新
    if "name" in updates:
        program.name = updates["name"]
    if "sample_rate" in updates:
        program.sample_rate = updates["sample_rate"]
    if "stages" in updates:
        program.stages = [Stage(**s) if isinstance(s, dict) else s for s in updates["stages"]]

    save_program_to_disk(program)
    return program


@app.delete("/api/programs/{program_id}")
async def delete_program(program_id: str):
    """プログラム削除"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")
    del programs_db[program_id]
    delete_program_from_disk(program_id)
    return {"message": "Program deleted"}


# ===== ステージ管理 API =====

@app.post("/api/programs/{program_id}/stages")
async def add_stage(program_id: str, stage: Stage) -> Program:
    """ステージ追加"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    program.stages.append(stage)
    save_program_to_disk(program)
    return program


@app.delete("/api/programs/{program_id}/stages/{stage_idx}")
async def delete_stage(program_id: str, stage_idx: int) -> Program:
    """ステージ削除"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    program.stages.pop(stage_idx)
    save_program_to_disk(program)
    return program


# ===== トラック管理 API =====

@app.post("/api/programs/{program_id}/stages/{stage_idx}/tracks")
async def add_track(program_id: str, stage_idx: int, track: Track) -> Program:
    """トラック追加"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    stage = program.stages[stage_idx]
    stage.tracks.append(track)
    save_program_to_disk(program)
    return program


@app.delete("/api/programs/{program_id}/stages/{stage_idx}/tracks/{track_idx}")
async def delete_track(program_id: str, stage_idx: int, track_idx: int) -> Program:
    """トラック削除"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    stage = program.stages[stage_idx]
    if track_idx < 0 or track_idx >= len(stage.tracks):
        raise HTTPException(status_code=404, detail="Track not found")

    stage.tracks.pop(track_idx)
    save_program_to_disk(program)
    return program


@app.put("/api/programs/{program_id}/stages/{stage_idx}/tracks/{track_idx}")
async def update_track(program_id: str, stage_idx: int, track_idx: int, track: Track) -> Program:
    """トラック更新"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    stage = program.stages[stage_idx]
    if track_idx < 0 or track_idx >= len(stage.tracks):
        raise HTTPException(status_code=404, detail="Track not found")

    stage.tracks[track_idx] = track
    save_program_to_disk(program)
    return program


# ===== 再生 API =====

def _play_program_task(program_id: str):
    """プログラム再生タスク（ステージごとに再生、スキップ対応）"""
    global playback_status, is_playing, current_program_id, skip_to_stage
    import time as time_module

    program = programs_db[program_id]
    generator = AudioGenerator(sample_rate=program.sample_rate)
    current_program_id = program_id

    # 総時間を計算
    total_time = sum(stage.duration for stage in program.stages)
    playback_status.total_time = total_time
    playback_status.is_playing = True
    is_playing = True

    # 事前に全ステージの音声を生成
    stage_audios = []
    for stage in program.stages:
        stage_audio = generate_audio_for_stage(stage, generator)
        stage_audios.append(stage_audio)

    stage_idx = 0
    elapsed_before_current = 0.0

    while stage_idx < len(program.stages) and is_playing:
        # スキップ要求チェック
        if skip_to_stage is not None:
            stage_idx = skip_to_stage
            skip_to_stage = None
            elapsed_before_current = sum(program.stages[i].duration for i in range(stage_idx))
            stop_current_playback_audio()
            continue

        if not is_playing:
            break

        stage = program.stages[stage_idx]
        playback_status.current_stage = stage_idx

        # ステージの音声を再生
        stage_audio = stage_audios[stage_idx]

        # 再生時間追跡用スレッド
        stage_start_time = time_module.time()
        stage_duration = stage.duration
        current_elapsed_before = elapsed_before_current

        def update_stage_elapsed():
            while is_playing:
                if skip_to_stage is not None:
                    break
                elapsed_in_stage = time_module.time() - stage_start_time
                if elapsed_in_stage >= stage_duration:
                    break
                playback_status.elapsed_time = current_elapsed_before + min(elapsed_in_stage, stage_duration)
                time_module.sleep(0.1)

        tracker = threading.Thread(target=update_stage_elapsed, daemon=True)
        tracker.start()

        # ステージ再生
        play_audio_realtime(stage_audio, generator.sample_rate)

        # スキップされた場合はcontinue
        if skip_to_stage is not None:
            continue

        # 次のステージへ
        elapsed_before_current += stage.duration
        stage_idx += 1

    # 再生完了
    playback_status.is_playing = False
    is_playing = False
    current_program_id = None


@app.post("/api/play/{program_id}")
async def play_program(program_id: str, backend: str = None):
    """プログラムをリアルタイム再生"""
    global AUDIO_BACKEND

    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    # 再生中の場合は拒否
    if is_playing:
        raise HTTPException(status_code=409, detail="Already playing. Stop current playback first.")

    # バックエンドを一時的に変更
    if backend and backend in ["paplay", "sounddevice"]:
        AUDIO_BACKEND = backend

    # バックグラウンドで再生
    executor.submit(_play_program_task, program_id)

    return {"message": "Playback started"}


@app.get("/api/status")
async def get_status() -> PlaybackStatus:
    """再生ステータス取得"""
    playback_status.is_playing = is_playing
    return playback_status


@app.post("/api/stop")
async def stop_playback():
    """再生停止"""
    stop_current_playback()
    return {"message": "Playback stopped"}


@app.post("/api/prev")
async def prev_stage():
    """前のステージへ移動"""
    global skip_to_stage

    if not is_playing or current_program_id is None:
        return {"message": "Not playing", "current_stage": 0}

    program = programs_db.get(current_program_id)
    if not program:
        return {"message": "Program not found", "current_stage": 0}

    new_stage = max(0, playback_status.current_stage - 1)
    skip_to_stage = new_stage
    stop_current_playback_audio()

    return {"message": "Skipping to previous stage", "current_stage": new_stage}


@app.post("/api/next")
async def next_stage():
    """次のステージへ移動"""
    global skip_to_stage

    if not is_playing or current_program_id is None:
        return {"message": "Not playing", "current_stage": 0}

    program = programs_db.get(current_program_id)
    if not program:
        return {"message": "Program not found", "current_stage": 0}

    new_stage = min(len(program.stages) - 1, playback_status.current_stage + 1)
    skip_to_stage = new_stage
    stop_current_playback_audio()

    return {"message": "Skipping to next stage", "current_stage": new_stage}


def _play_stage_task(program_id: str, stage_idx: int):
    """ステージ再生タスク（バックグラウンド実行用）"""
    program = programs_db[program_id]
    generator = AudioGenerator(sample_rate=program.sample_rate)
    stage = program.stages[stage_idx]

    # ステージの音声を生成
    stage_audio = generate_audio_for_stage(stage, generator)

    # リアルタイム再生
    play_audio_realtime(stage_audio, generator.sample_rate)


@app.post("/api/play/stage/{program_id}/{stage_idx}")
async def play_stage(program_id: str, stage_idx: int, backend: str = None):
    """ステージを再生"""
    global AUDIO_BACKEND

    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    # 再生中の場合は拒否
    if is_playing:
        raise HTTPException(status_code=409, detail="Already playing. Stop current playback first.")

    # バックエンドを一時的に変更
    if backend and backend in ["paplay", "sounddevice"]:
        AUDIO_BACKEND = backend

    # バックグラウンドで再生
    executor.submit(_play_stage_task, program_id, stage_idx)

    return {"message": "Stage playback started"}


def _play_track_task(program_id: str, stage_idx: int, track_idx: int):
    """トラック再生タスク（バックグラウンド実行用）"""
    program = programs_db[program_id]
    generator = AudioGenerator(sample_rate=program.sample_rate)
    stage = program.stages[stage_idx]
    track = stage.tracks[track_idx]

    # トラックの音声を生成（ステージのdurationを使用）
    track_audio = generate_audio_for_track(track, stage.duration, generator)

    # リアルタイム再生
    play_audio_realtime(track_audio, generator.sample_rate)


@app.post("/api/play/track/{program_id}/{stage_idx}/{track_idx}")
async def play_track(program_id: str, stage_idx: int, track_idx: int, backend: str = None):
    """トラック単体を再生"""
    global AUDIO_BACKEND

    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    stage = program.stages[stage_idx]
    if track_idx < 0 or track_idx >= len(stage.tracks):
        raise HTTPException(status_code=404, detail="Track not found")

    # 再生中の場合は拒否
    if is_playing:
        raise HTTPException(status_code=409, detail="Already playing. Stop current playback first.")

    # バックエンドを一時的に変更
    if backend and backend in ["paplay", "sounddevice"]:
        AUDIO_BACKEND = backend

    # バックグラウンドで再生
    executor.submit(_play_track_task, program_id, stage_idx, track_idx)

    return {"message": "Track playback started"}


# ===== 波形表示 API =====

@app.get("/api/waveform/data/stage/{program_id}/{stage_idx}")
async def get_stage_waveform_data(program_id: str, stage_idx: int, full: bool = False):
    """ステージの波形データを取得（JSON形式）

    Args:
        full: Trueの場合、全サンプルを返す（Web Audio再生用）
    """
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    generator = AudioGenerator(sample_rate=program.sample_rate)
    stage = program.stages[stage_idx]

    # ステージの音声を生成
    stage_audio = generate_audio_for_stage(stage, generator)

    if full:
        # 全サンプルを返す（Web Audio再生用）
        audio_data = stage_audio.tolist()
    else:
        # ダウンサンプリング（表示用）
        max_samples = 5000
        if len(stage_audio) > max_samples:
            step = len(stage_audio) // max_samples
            audio_data = stage_audio[::step].tolist()
        else:
            audio_data = stage_audio.tolist()

    return {
        "waveform": audio_data,
        "duration": stage.duration,
        "sample_rate": generator.sample_rate
    }


@app.get("/api/waveform/data/program/{program_id}")
async def get_program_waveform_data(program_id: str):
    """プログラム全体の波形データを取得（Web Audio再生用）"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    generator = AudioGenerator(sample_rate=program.sample_rate)

    # 全ステージの音声を生成して連結
    all_audio = []
    for stage in program.stages:
        stage_audio = generate_audio_for_stage(stage, generator)
        all_audio.append(stage_audio)

    # 連結
    if all_audio:
        combined_audio = np.concatenate(all_audio)
    else:
        combined_audio = np.zeros(generator.sample_rate, dtype=np.float32)

    # 総再生時間を計算
    total_duration = sum(stage.duration for stage in program.stages)

    return {
        "waveform": combined_audio.tolist(),
        "duration": total_duration,
        "sample_rate": generator.sample_rate
    }


@app.get("/api/waveform/data/track/{program_id}/{stage_idx}/{track_idx}")
async def get_track_waveform_data(program_id: str, stage_idx: int, track_idx: int):
    """トラックの波形データを取得（Web Audio再生用）"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    if stage_idx < 0 or stage_idx >= len(program.stages):
        raise HTTPException(status_code=404, detail="Stage not found")

    stage = program.stages[stage_idx]
    if track_idx < 0 or track_idx >= len(stage.tracks):
        raise HTTPException(status_code=404, detail="Track not found")

    generator = AudioGenerator(sample_rate=program.sample_rate)
    track = stage.tracks[track_idx]

    # トラックの音声を生成
    track_audio = generate_audio_for_track(track, stage.duration, generator)

    return {
        "waveform": track_audio.tolist(),
        "duration": stage.duration,
        "sample_rate": generator.sample_rate
    }


# ===== エクスポート API =====

@app.get("/api/export/{program_id}")
async def export_program(program_id: str, filename: str = None):
    """プログラムをWAVファイルにエクスポート"""
    if program_id not in programs_db:
        raise HTTPException(status_code=404, detail="Program not found")

    program = programs_db[program_id]
    generator = AudioGenerator(sample_rate=program.sample_rate)

    # 全ステージの音声を生成して連結
    all_audio = []
    for stage in program.stages:
        stage_audio = generate_audio_for_stage(stage, generator)
        all_audio.append(stage_audio)

    # 連結
    if all_audio:
        combined_audio = np.concatenate(all_audio)
    else:
        combined_audio = np.zeros(generator.sample_rate, dtype=np.float32)

    # ファイル名を決定
    export_name = filename if filename else program.name

    # WAVファイルとして保存
    output_file = EXPORTS_DIR / f"{export_name}_{program.id}.wav"
    audio_int16 = np.int16(combined_audio * 32767)
    wavfile.write(str(output_file), generator.sample_rate, audio_int16)

    return FileResponse(
        path=str(output_file),
        media_type="audio/wav",
        filename=f"{export_name}.wav"
    )


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="音波洗浄システム")
    parser.add_argument(
        "--backend",
        choices=["paplay", "sounddevice"],
        default="paplay",
        help="オーディオバックエンド (デフォルト: paplay)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="ホストアドレス (デフォルト: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="ポート番号 (デフォルト: 8000)"
    )

    args = parser.parse_args()

    # グローバル変数を更新
    AUDIO_BACKEND = args.backend

    print(f"Audio Backend: {AUDIO_BACKEND}")
    print(f"Server: http://{args.host}:{args.port}")
    print()

    uvicorn.run(app, host=args.host, port=args.port)
