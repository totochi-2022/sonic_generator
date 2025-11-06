"""データモデル定義"""
from pydantic import BaseModel, Field
from typing import Literal, Optional, List


class Track(BaseModel):
    """トラック定義"""
    type: Literal["tone", "sweep", "wave_file"]
    volume: float = Field(default=0.7, ge=0.0, le=1.0, description="音量")
    enabled: bool = Field(default=True, description="有効/無効")

    # tone/sweep用
    frequency: Optional[int] = Field(None, ge=20, le=40000)
    wave_type: Optional[Literal["triangle", "sine", "square"]] = None
    sweep_start: Optional[int] = Field(None, ge=20, le=40000)
    sweep_end: Optional[int] = Field(None, ge=20, le=40000)
    sweep_period: Optional[float] = Field(None, gt=0)

    # wave_file用
    file_path: Optional[str] = None
    play_mode: Optional[Literal["once", "repeat"]] = None
    repeat_period: Optional[float] = Field(None, gt=0)

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tone",
                "frequency": 600,
                "wave_type": "triangle",
                "duration": 30,
                "volume": 0.7
            }
        }


class Stage(BaseModel):
    """ステージ定義"""
    name: str
    duration: float = Field(default=30.0, gt=0, description="ステージの再生時間(秒)")
    tracks: List[Track] = Field(default_factory=list, max_length=5)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "ステージ1",
                "duration": 30.0,
                "tracks": []
            }
        }


class Program(BaseModel):
    """プログラム定義"""
    id: Optional[str] = None
    name: str
    stages: List[Stage] = Field(default_factory=list, max_length=5)
    sample_rate: int = Field(default=44100)
    normalize_mode: Literal["peak", "clip", "none"] = Field(
        default="clip",
        description="正規化モード: peak=常に1.0, clip=超過時のみ, none=なし"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "音波洗浄プログラム1",
                "stages": [],
                "sample_rate": 44100,
                "normalize_mode": "peak"
            }
        }


class PlaybackStatus(BaseModel):
    """再生ステータス"""
    is_playing: bool = False
    current_stage: int = 0
    current_track: int = 0
    elapsed_time: float = 0.0
    total_time: float = 0.0
