# 音波洗浄システム 仕様書

## 1. プロジェクト概要

音波洗浄用の音声生成・再生システム。周波数・波形・時間を指定したプログラムを作成し、リアルタイム再生またはWAVファイル出力を行う。

## 2. 開発環境

- **OS**: WSL2 (wslg使用)
- **言語**: Python 3.10+
- **フレームワーク**: FastAPI
- **フロントエンド**: htmx
- **音声処理**: sounddevice, numpy, scipy

## 3. システム構造

### 3.1 階層構造
```
プログラム (Program)
  └─ ステージ (Stage) ×最大5個
       └─ トラック (Track) ×最大5個
```

### 3.2 データモデル

#### Track (トラック)

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| type | "tone" \| "sweep" \| "wave_file" | ✓ | トラック種類 |
| duration | float | ✓ | 再生時間（秒） |
| volume | float | ✓ | 音量（0.0-1.0、デフォルト0.7） |
| frequency | int | △ | 周波数（Hz、tone用） |
| wave_type | "triangle" \| "sine" \| "square" | △ | 波形（tone/sweep用） |
| sweep_start | int | △ | 開始周波数（Hz、sweep用） |
| sweep_end | int | △ | 終了周波数（Hz、sweep用） |
| sweep_period | float | △ | スイープ周期（秒、sweep用） |
| file_path | str | △ | ファイルパス（wave_file用） |
| play_mode | "once" \| "repeat" | △ | 再生モード（wave_file用） |
| repeat_period | float | △ | リピート周期（秒、wave_file用） |

#### Stage (ステージ)

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| name | str | ✓ | ステージ名 |
| tracks | List[Track] | ✓ | トラックリスト（最大5個） |

#### Program (プログラム)

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| name | str | ✓ | プログラム名 |
| stages | List[Stage] | ✓ | ステージリスト（最大5個） |
| sample_rate | int | ✓ | サンプリングレート（デフォルト44100） |

## 4. トラック種類

### 4.1 トーン (tone)

指定周波数の連続音を生成

**パラメータ:**
- frequency: 20-40000 Hz
- wave_type: triangle / sine / square
- duration: 秒
- volume: 0.0-1.0

**例:**
```json
{
  "type": "tone",
  "frequency": 600,
  "wave_type": "triangle",
  "duration": 30,
  "volume": 0.7
}
```

### 4.2 スイープ (sweep)

周波数を時間変化させる

**パラメータ:**
- sweep_start: 20-40000 Hz
- sweep_end: 20-40000 Hz
- sweep_period: 秒（1周期の時間）
- wave_type: triangle / sine / square
- duration: 秒
- volume: 0.0-1.0

**例:**
```json
{
  "type": "sweep",
  "sweep_start": 400,
  "sweep_end": 800,
  "sweep_period": 10,
  "wave_type": "triangle",
  "duration": 60,
  "volume": 0.7
}
```

### 4.3 WAVファイル (wave_file)

外部WAVファイルを再生

**パラメータ:**
- file_path: ファイルパス
- play_mode: once（1回のみ） / repeat（繰り返し）
- repeat_period: 秒（repeatモード時の周期）
- duration: 秒
- volume: 0.0-1.0

**例:**
```json
{
  "type": "wave_file",
  "file_path": "/path/to/audio.wav",
  "play_mode": "repeat",
  "repeat_period": 5,
  "duration": 60,
  "volume": 0.5
}
```

## 5. 機能要件

### 5.1 プログラム管理

- [ ] プログラム作成
- [ ] プログラム保存（JSON形式）
- [ ] プログラム読み込み
- [ ] プログラム削除
- [ ] プログラム一覧表示

### 5.2 ステージ管理

- [ ] ステージ追加（最大5個）
- [ ] ステージ削除
- [ ] ステージ編集（名前変更）
- [ ] ステージ順序変更

### 5.3 トラック管理

- [ ] トラック追加（各ステージ最大5個）
- [ ] トラック削除
- [ ] トラック編集
- [ ] トラック順序変更

### 5.4 再生機能

- [ ] リアルタイム再生（sounddevice使用）
- [ ] 一時停止 / 再開
- [ ] 停止
- [ ] 進捗表示（現在のステージ・トラック、残り時間）

### 5.5 エクスポート機能

- [ ] プログラム全体をWAVファイルに出力
- [ ] サンプリングレート選択
  - 44.1kHz
  - 48kHz
  - 96kHz
  - 192kHz
  - 384kHz

## 6. ディレクトリ構造
```
audio-cleaning-system/
├── app.py                      # FastAPIメインアプリ
├── audio_generator.py          # 音声生成クラス
├── models.py                   # Pydanticデータモデル
├── requirements.txt            # 依存パッケージ
├── README.md                   # プロジェクト説明
├── static/
│   └── style.css              # スタイルシート
├── templates/
│   ├── index.html             # プログラム一覧ページ
│   ├── program.html           # プログラム編集ページ
│   └── components/            # htmxコンポーネント
│       ├── stage_list.html
│       ├── track_form.html
│       └── player.html
├── programs/                   # プログラムJSON保存ディレクトリ
└── exports/                    # WAVファイル出力ディレクトリ
```

## 7. API仕様

### 7.1 プログラム管理
```
GET    /                        プログラム一覧ページ
GET    /programs                プログラム一覧取得（JSON）
POST   /programs                プログラム作成
GET    /programs/{id}           プログラム詳細取得
PUT    /programs/{id}           プログラム更新
DELETE /programs/{id}           プログラム削除
```

### 7.2 ステージ管理
```
POST   /programs/{id}/stages           ステージ追加
DELETE /programs/{id}/stages/{idx}     ステージ削除
PUT    /programs/{id}/stages/{idx}     ステージ更新
```

### 7.3 トラック管理
```
POST   /programs/{id}/stages/{idx}/tracks              トラック追加
DELETE /programs/{id}/stages/{idx}/tracks/{track_idx}  トラック削除
PUT    /programs/{id}/stages/{idx}/tracks/{track_idx}  トラック更新
```

### 7.4 再生・エクスポート
```
POST   /play/{id}               プログラム再生開始
POST   /pause                   一時停止
POST   /resume                  再開
POST   /stop                    停止
GET    /status                  再生ステータス取得
POST   /export/{id}             WAVファイルエクスポート
```

## 8. UI要件

### 8.1 プログラム一覧ページ (/)

- プログラム一覧表示（カード形式）
- 各プログラムに以下のボタン
  - 編集
  - 再生
  - エクスポート
  - 削除
- 新規プログラム作成ボタン

### 8.2 プログラム編集ページ (/program/{id})

**ステージセクション:**
- ステージリスト表示
- ステージ追加ボタン
- 各ステージに削除ボタン

**トラック編集フォーム:**
- トラック種類選択（トーン/スイープ/WAVファイル）
- 時間入力（秒）
- 音量スライダー（0-100%表示、内部0.0-1.0）
- 周波数入力（Hz）
- 波形選択（三角波/正弦波/矩形波）
- スイープパラメータ（種類がsweepの場合）
- WAVファイル選択（種類がwave_fileの場合）
- 追加ボタン

**トラックリスト:**
- 各トラックの情報表示
- 編集/削除ボタン

**プレイヤーコントロール:**
- 再生/一時停止/停止ボタン
- 進捗バー
- 現在のステージ・トラック表示

### 8.3 エクスポート設定

- サンプリングレート選択
- ファイル名入力
- エクスポート実行ボタン

## 9. データモデル実装例（Pydantic）
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class Track(BaseModel):
    """トラック定義"""
    type: Literal["tone", "sweep", "wave_file"]
    duration: float = Field(gt=0, description="時間(秒)")
    volume: float = Field(default=0.7, ge=0.0, le=1.0, description="音量")

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

class Stage(BaseModel):
    """ステージ定義"""
    name: str
    tracks: List[Track] = Field(default_factory=list, max_length=5)

class Program(BaseModel):
    """プログラム定義"""
    name: str
    stages: List[Stage] = Field(default_factory=list, max_length=5)
    sample_rate: int = Field(default=44100)
```

## 10. 実装優先順位

### Phase 1: コア機能（必須）
1. AudioGeneratorクラス実装
   - トーン生成
   - スイープ生成
   - WAVファイル読み込み
   - 音量調整機能
2. FastAPIアプリ基本構造
3. データモデル（models.py）
4. リアルタイム再生機能

### Phase 2: UI（必須）
5. プログラム一覧ページ
6. プログラム編集ページ
7. トラック追加/削除UI
8. ステージ管理UI
9. 音量スライダー

### Phase 3: 完成（必須）
10. プログラム保存/読み込み（JSON）
11. WAVファイルエクスポート
12. 再生コントロール（一時停止/再開）
13. 進捗表示

### Phase 4: 追加機能（オプション）
14. プログラムテンプレート
15. プレビュー機能
16. エラーハンドリング強化

## 11. 依存パッケージ
```txt
fastapi
uvicorn[standard]
python-multipart
jinja2
sounddevice
numpy
scipy
pydantic
```

## 12. 注意事項

- WSL2環境でsounddeviceを使用するため、wslgが有効であること
- 音量は0.0-1.0で内部管理し、UIでは0-100%で表示
- プログラムファイルはJSON形式で保存
- サンプリングレートは出力時に指定可能
- トラックは各ステージ内で順次実行される
- ステージはプログラム内で順次実行される

## 13. 実装開始手順

1. プロジェクトディレクトリ作成
2. 仮想環境セットアップ
3. 依存パッケージインストール
4. AudioGeneratorクラス実装
5. FastAPIアプリ基本構造実装
6. 段階的に機能追加

---

**バージョン**: 1.0
**作成日**: 2025-01-31
