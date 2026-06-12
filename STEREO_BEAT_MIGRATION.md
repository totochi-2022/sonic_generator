# sonic_generator ステレオ2ch + うなり(beat)方式 移行指示書（確定版）

## 目的
エキサイター運用に **2つのモード** を持たせ、UIで使い分ける:

- **mono モード（1個運用）**: L=R の同一信号。エキサイター1台、または
  **別容器に2台を置いて同じ信号で同時駆動**するケース。
- **beat モード（2個運用）**: L/R に**わずかに異なる周波数**を与え、その差(Δf=うなり)で
  **同一容器内**の音響の腹/節を**横方向に自動走査**する。節が動き続け、洗浄の死点が時間平均で消える。

出力は**どちらのモードでも常に2ch WAV**（mono は L=R を書き出すだけ）。

## 中心となる原理（beat モード）
- L = 中心周波数 − Δf/2、 R = 中心周波数 + Δf/2
- **Δf(左右の周波数差)= うなり = 節の走査速度**を決める
- 中心周波数をスイープしても、**Δf を保てば**節の走査は途切れず継続する
- 節の位置は **Δf の積分(累積位相差)** で決まる → 位相は L/R とも **cumsum で積分**する

数学的に: 周波数差Δfを与える = 位相差が 2π·∫Δf dt のレートで増え続ける
（Δf一定なら位相差は一定レートで増加 = 節が一定速度で走査。実証済み: Δf=0.3Hzで10秒 → 位相差3.0回転）

---

## モード設計（確定）

| | **mono（1個運用）** | **beat（2個運用）** |
|---|---|---|
| L/R信号 | **L = R（同一波形）** | L=fc−Δf/2, R=fc+Δf/2 |
| 物理セットアップ | 1台、または別容器2台に同信号 | 同一容器に2台、節を横走査 |
| delta_f | **無視（実効0に強制）** | 有効（符号付き） |
| 出力 | 2ch WAV（L=R） | 2ch WAV（L≠R） |

- **モードはプログラム全体に1個** 持つ（`Program.mode`）。
- 出力は常に2ch。mono と beat の差はL/Rが同一かどうかだけ。
- mono モードでは generate 経路で delta_f を実効0として扱う（L=R）。

---

## Δf の仕様（確定 / トラックごと・符号付き）

- delta_f は**トラックごと**に持つ（同一ステージに 80Hz/Δf別、400Hz/Δf別 を同居可）。
- **符号付き**（負を許可）。Δf が 0 をまたぐと節が一旦止まり**逆方向**に走る = **左右往復走査**。
- Δf 自体を**時間スイープ**できる（`delta_f → delta_f_end` を周期 `delta_f_period` で往復）。
  - 例: −0.5 → +0.5 で振る → 節が左右に往復しながら全域を走査。
  - delta_f_end 未設定 → Δf 一定（従来挙動）。
- **重要**: Δf がスイープすると tone でも L/R 周波数が時間変化するため、
  **tone/sweep とも位相は cumsum で積分する**（`2π·f·t` の直接式は使わない）。

---

## 1. models.py

### 1-1. Program に mode を追加
```python
class Program(BaseModel):
    id: Optional[str] = None
    name: str
    mode: Literal["mono", "beat"] = Field(default="mono", description="mono=1個運用(L=R) / beat=2個運用(うなり)")
    stages: List[Stage] = Field(default_factory=list)
    sample_rate: int = Field(default=44100)
```
mode 未指定の既存プログラム → "mono"（後方互換: L=R の2ch = 従来モノラル相当）。

### 1-2. Track に delta_f 系を追加（符号付き・スイープ対応）
```python
# beat方式: L/R周波数差[Hz]。符号が走査の向き、絶対値が走査速度。
# mono モードでは無視される。0.0 = L/R同一。推奨レンジ |Δf| 0.1〜1.0Hz。
delta_f: float = Field(default=0.0, description="L/R周波数差[Hz](一定値 or スイープ開始値、符号付き)")
delta_f_end: Optional[float] = Field(default=None, description="設定時Δfをここまでスイープ(往復)")
delta_f_period: Optional[float] = Field(default=None, gt=0, description="Δfスイープ周期[秒](fcのsweep_periodと独立)")
```
※ `ge=0.0` 制約は**付けない**（負値許可）。delta_f_end=None なら一定Δf。

---

## 2. audio_generator.py — ステレオ + うなり対応（最重要）

### 2-1. 波形ヘルパー（共通化）
```python
def _wave(self, wave_type, phase):
    if wave_type == "sine":
        return np.sin(phase)
    elif wave_type == "square":
        return signal.square(phase)
    elif wave_type == "triangle":
        return signal.sawtooth(phase, width=0.5)
    raise ValueError(f"Unsupported wave type: {wave_type}")
```

### 2-2. Δf 配列ヘルパー（一定 or スイープ）
```python
def _delta_f_array(self, t, delta_f, delta_f_end, delta_f_period):
    """瞬時Δf(t)を返す。delta_f_end=None なら一定。"""
    if delta_f_end is None or delta_f_period is None:
        return np.full_like(t, delta_f)
    # raised-cosine で delta_f <-> delta_f_end を滑らかに往復(fcスイープと同形)
    ph = (t % delta_f_period) / delta_f_period
    ph = (1 - np.cos(2 * np.pi * ph)) / 2          # 0->1->0
    return delta_f + (delta_f_end - delta_f) * ph
```

### 2-3. 中心周波数→ステレオ生成の共通コア（cumsum 一本化）
tone も sweep も「fc(t) 配列」を作って同じコアに通す。Δf は常に符号付きの瞬時配列。
```python
def _render_stereo(self, fc, t, wave_type, volume, delta_f, delta_f_end, delta_f_period):
    df = self._delta_f_array(t, delta_f, delta_f_end, delta_f_period)   # (n,)
    fL = fc - df / 2.0
    fR = fc + df / 2.0
    phase_L = 2 * np.pi * np.cumsum(fL) / self.sample_rate   # うなりは位相差に自動的に出る
    phase_R = 2 * np.pi * np.cumsum(fR) / self.sample_rate
    left  = self._wave(wave_type, phase_L)
    right = self._wave(wave_type, phase_R)
    stereo = np.stack([left, right], axis=1) * volume        # (n,2)
    return stereo.astype(np.float32)
```

### 2-4. generate_tone（fc 一定）
```python
def generate_tone(self, frequency, duration, wave_type="triangle", volume=0.7,
                  delta_f=0.0, delta_f_end=None, delta_f_period=None):
    n_samples = int(self.sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    fc = np.full_like(t, float(frequency))
    return self._render_stereo(fc, t, wave_type, volume, delta_f, delta_f_end, delta_f_period)
```

### 2-5. generate_sweep（fc スイープ）
```python
def generate_sweep(self, sweep_start, sweep_end, sweep_period, duration,
                   wave_type="triangle", volume=0.7,
                   delta_f=0.0, delta_f_end=None, delta_f_period=None):
    n_samples = int(self.sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    sweep_phase = (t % sweep_period) / sweep_period
    sweep_phase = (1 - np.cos(2 * np.pi * sweep_phase)) / 2
    fc = sweep_start + (sweep_end - sweep_start) * sweep_phase   # 中心周波数(t)
    return self._render_stereo(fc, t, wave_type, volume, delta_f, delta_f_end, delta_f_period)
```
重要: cumsum によりスイープ中も瞬時Δfが保たれ、位相差が積分されて節が走査され続ける。

### 2-6. mix_tracks をステレオ対応
(n,2)同士を加算。**正規化はL/R共通の最大振幅で**（別々正規化は左右バランス/うなりを壊す）。
```python
@staticmethod
def mix_tracks(tracks: list[np.ndarray]) -> np.ndarray:
    if not tracks:
        raise ValueError("No tracks to mix")
    max_length = max(len(tr) for tr in tracks)
    padded = []
    for tr in tracks:
        if tr.ndim == 1:                          # 後方互換: モノラルは2chに複製
            tr = np.stack([tr, tr], axis=1)
        if len(tr) < max_length:
            tr = np.pad(tr, ((0, max_length - len(tr)), (0, 0)), mode="constant")
        padded.append(tr)
    mixed = np.sum(padded, axis=0)                # (n,2)
    peak = np.max(np.abs(mixed))                  # L/R共通スケール(重要)
    if peak > 1.0:
        mixed = mixed / peak
    return mixed.astype(np.float32)
```

---

## 3. app.py — モード伝播・再生・エクスポート・APIのステレオ対応

### 3-0. モードを generate 経路に伝播
`generate_audio_for_track` / `generate_audio_for_stage` に `mode` を渡す。
mono のときは delta_f 系を実効0にする（L=R）。
```python
def generate_audio_for_track(track, duration, generator, mode="mono"):
    # mono: L=RにするためΔfを無効化
    df      = 0.0  if mode == "mono" else track.delta_f
    df_end  = None if mode == "mono" else track.delta_f_end
    df_per  = None if mode == "mono" else track.delta_f_period

    if track.type == "tone":
        return generator.generate_tone(
            frequency=track.frequency, duration=duration,
            wave_type=track.wave_type, volume=track.volume,
            delta_f=df, delta_f_end=df_end, delta_f_period=df_per,
        )
    elif track.type == "sweep":
        return generator.generate_sweep(
            sweep_start=track.sweep_start, sweep_end=track.sweep_end,
            sweep_period=track.sweep_period, duration=duration,
            wave_type=track.wave_type, volume=track.volume,
            delta_f=df, delta_f_end=df_end, delta_f_period=df_per,
        )
    elif track.type == "wave_file":
        raise NotImplementedError("wave_file type not yet implemented")
```
`generate_audio_for_stage(stage, generator, mode)` も mode を受けて track 呼び出しに渡す。
各APIで `mode=program.mode` を渡す。

### 3-1. 空ステージの無音を (n,2) に
```python
return np.zeros((int(generator.sample_rate * stage.duration), 2), dtype=np.float32)
```

### 3-2. play_audio_realtime（paplay経路）— int16+clip保護
(n,2)のint16をwavfile.writeに渡せばステレオWAV。**clip保護を追加**:
```python
audio_int16 = np.int16(np.clip(audio_data, -1.0, 1.0) * 32767)   # (n,2)でOK
wavfile.write(tmp_path, sample_rate, audio_int16)
```
paplayはステレオWAVを自動で2ch再生。L=ch0→エキサイター1, R=ch1→エキサイター2。

### 3-3. play_audio_realtime（sounddevice経路）
`sd.play(audio_data, sample_rate)` は (n,2) をそのままステレオ再生。出力デバイスが2ch以上であること。

### 3-4. エクスポート（export_program）
np.concatenate(all_audio) は (n,2) 同士で軸0連結OK。**int16化に clip 保護を追加**（3-2と対称に）:
```python
audio_int16 = np.int16(np.clip(combined_audio, -1.0, 1.0) * 32767)
wavfile.write(str(output_file), generator.sample_rate, audio_int16)
```
空時 np.zeros(...) を (n,2) に。

### 3-5. 波形API — **`full` で分岐（重要・指示書旧版の誤りを修正）**
`/api/waveform/data/...?full=true` は**ブラウザでの実再生**に使われる（表示専用ではない）。
- **full=true（再生用）**: `(n,2)` を**そのまま**返す（ネスト配列）。フロントが2chで鳴らす。
- **full=false（表示グラフ用）**: L ch を1D化してダウンサンプリング。

```python
if full:
    audio_data = stage_audio.tolist()                     # (n,2) のまま
else:
    wf = stage_audio[:, 0] if stage_audio.ndim == 2 else stage_audio   # 表示はL chで十分
    max_samples = 5000
    if len(wf) > max_samples:
        step = len(wf) // max_samples
        audio_data = wf[::step].tolist()
    else:
        audio_data = wf.tolist()
```
program 全体／track の波形APIも同様（再生用途なら (n,2) のまま返す）。
レスポンスに `"channels": 2` を含めるとフロントが判定しやすい。

---

## 4. フロント（templates/program.html）

### 4-1. Web Audio を**真ステレオ再生**に（指示書旧版が未対応だった箇所）
現状 `createBuffer(1, ...)` のモノラル固定。`(n,2)` を2chで鳴らすよう変更:
```js
async function playWithWebAudio(audioData, sampleRate) {
    stopWebAudio();
    const ctx = getAudioContext();
    if (ctx.state === 'suspended') await ctx.resume();

    // audioData が [[L,R],[L,R],...] (2ch) か [v,v,...] (1ch) かを判定
    const isStereo = Array.isArray(audioData[0]);
    const n = audioData.length;
    const buffer = ctx.createBuffer(isStereo ? 2 : 1, n, sampleRate);
    if (isStereo) {
        const L = buffer.getChannelData(0), R = buffer.getChannelData(1);
        for (let i = 0; i < n; i++) { L[i] = audioData[i][0]; R[i] = audioData[i][1]; }
    } else {
        buffer.getChannelData(0).set(new Float32Array(audioData));
    }
    currentGainNode = ctx.createGain();
    currentGainNode.connect(ctx.destination);
    currentSource = ctx.createBufferSource();
    currentSource.buffer = buffer;
    currentSource.connect(currentGainNode);
    currentSource.onended = () => { currentSource = null; currentGainNode = null; };
    currentSource.start();
}
```

### 4-2. モード切替UI（プログラム単位）
プログラム設定に **mono / beat** のトグル（ラジオ or セレクト）を追加。
- mono → トラックの Δf 入力は無効化（グレーアウト）
- beat → Δf 入力群を有効化

### 4-3. トラック編集UIに Δf 系を追加（beat時のみ有効）
- `delta_f`（数値, 例 −2〜+2Hz, 0.05刻み）ラベル「うなり Δf [Hz](符号=向き, 絶対値=速度)」
- `delta_f_end`（任意, 空=一定）＋ `delta_f_period`（任意, 秒）ラベル「Δfスイープ(往復): 終値 / 周期」
- add_track / update_track のJSON送信に delta_f / delta_f_end / delta_f_period を含める
- 既存トラック（未指定）は delta_f=0 → 後方互換

（任意）プリセット: 「80Hz Δf=0.3」「400Hz Δf=0.5」「Δf往復 −0.5↔+0.5 周期20s」など。

---

## 5. テスト手順
### 5-1. tone うなり（一定Δf）
```python
g = AudioGenerator(44100)
a = g.generate_tone(80, 10.0, "sine", 0.7, delta_f=0.3)
assert a.shape == (441000, 2)
# L+R の包絡がうなる。うなり周期 = 1/Δf = 3.33s
```
### 5-2. mono相当（delta_f=0 → L=R）
```python
a = g.generate_tone(80, 1.0, "sine", 0.7, delta_f=0.0)
assert np.allclose(a[:, 0], a[:, 1])     # L==R
```
### 5-3. sweep+うなり（Δf保持）
```python
a = g.generate_sweep(60, 100, 5.0, 10.0, "sine", 0.7, delta_f=0.3)
# 中心60->100Hzスイープ中もL/R差0.3Hzを維持。位相差10秒で3.0回転
```
### 5-4. Δfスイープ（符号またぎ＝往復）
```python
a = g.generate_sweep(80, 80, 5.0, 20.0, "sine", 0.7,
                     delta_f=-0.5, delta_f_end=0.5, delta_f_period=20.0)
# Δfが -0.5↔+0.5 を往復。Δf=0付近で節が止まり向きが反転(左右往復走査)
```
### 5-5. mix（うなりトラックを複数）
80Hz(Δf=0.3) + 400Hz(Δf=0.5) を mix → (n,2)、peak<=1.0。
### 5-6. 実機
- D級アンプ L/R → エキサイター2個（同一容器に横に離して設置）
- delta_f=0.3 で洗浄ムラが**ゆっくり横に動き続ける**のを確認
- Δf往復(−0.5↔+0.5)で節が**左右に往復**するのを確認
- mono モードに切替 → L=R、別容器2台でも同一挙動

---

## 6. 実装順序
1. models.py: Program に mode、Track に delta_f / delta_f_end / delta_f_period（土台）
2. audio_generator.py: _wave → _delta_f_array → _render_stereo → generate_tone/sweep → mix_tracks。5-1〜5-5を通す
3. app.py: generate_audio_for_track/_stage に mode 伝播 + 空ゼロを(n,2)化
4. play_audio_realtime / export の int16+clip（paplay/sounddeviceは(n,2)で自動ステレオ）
5. 波形APIの `full` 分岐（再生=2ch生 / 表示=L ch 1D）
6. program.html: Web Audio 真ステレオ化 → mode切替UI → Δf系UI
7. 実機で mono/beat 切替・Δf往復走査を確認（5-6）

---

## 7. パラメータの目安・注意
- **|Δf| = 0.1〜1.0Hz** 程度の僅差を推奨。うなり周期 = 1/|Δf| 秒。
  - Δf=0.3 → 3.3秒で1走査（ゆっくり、洗浄時間を確保）
  - |Δf|大（数Hz〜）→ 節が速すぎ、各位置の滞在が短く洗浄前に通過
  - |Δf|小（<0.1）→ 走査が遅く全域カバーに時間
- **符号**: Δf>0 と Δf<0 は走査の向きが逆。0をまたぐスイープで左右往復。
- **80Hz帯と400Hz帯は別トラックで各々別のΔf**設定可。
- **正規化はL/R共通スケール**（mix_tracksのpeak）。別々正規化は不可。
- **波長 ≫ 容器**（80Hz:約18m, 400Hz:約3.75m@水中1500m/s）。実際の節の動きは容器共鳴モード依存。理論は目安、実機でΔfを振って実測。
- **L/R割り当て**: ch0(L)=エキサイター1, ch1(R)=エキサイター2（逆でも走査の向きが反転するだけ）。
- 三角波/矩形波でも cumsum 位相にうなりが正しく乗る。

---

## 8. 旧「位相差方式」からの変更まとめ
- phase_diff / phase_sweep_* 系を**全廃**、代わりに **delta_f（符号付き）+ delta_f_end/period**
- **mono/beat の明示モード**をプログラムに追加（出力は常に2ch）
- tone/sweep とも **cumsum で位相積分**（Δfスイープに対応するため tone も直接式をやめる）
- **波形APIは full で分岐**（再生=2ch生データ / 表示=L ch 1D）。旧版の「L chで十分」は再生を壊すため不採用
- **フロント Web Audio を真ステレオ化**（createBuffer(2,…)）
- int16化に **clip 保護**（再生・エクスポート両方）
- mix/再生/エクスポート/API のステレオ対応
