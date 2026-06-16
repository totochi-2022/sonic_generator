/* Changelog: ヘッダーの What's New ボタンと更新履歴モーダル
 *
 * バージョン管理:
 *   - 表示バージョンは /api/version (= VERSION ファイル) から取得
 *   - ENTRIES (各バージョンの説明文) のみ手動更新
 *
 * リリース手順:
 *   1. このファイルの ENTRIES 先頭に新エントリを追加
 *   2. VERSION ファイルを新バージョンに更新
 *   3. コミット
 *   4. git tag vX.Y.Z (このコミットに対して)
 *   5. サーバ再起動 → /api/version が新バージョンを返す → 未読ドットが点く
 */

const Changelog = {
    // 最新バージョン (起動時に /api/version から取得)
    CURRENT: 'unknown',

    ENTRIES: [
        {
            version: 'v0.4.0',
            date: '2026-06-16',
            highlights: [
                'ステレオ2ch + うなり(beat)方式に対応 — プログラムごとに mono(1個運用・L=R) / beat(2個運用) を切替',
                'うなり Δf (L/R周波数差) で音響の節を横走査。Δf スイープ(0をまたぐ往復)で節を左右に往復走査',
                'Δf はトラックごとに設定可 (符号=向き / 絶対値=速度 / 一定 or スイープ)',
                'ブラウザ試聴を真ステレオ2ch再生に。エクスポートは常に2ch WAV (clip保護付き)',
                'プログラム一覧と WAV プレイヤーに mono / beat 判別バッジを表示 (WAVは中身のL≠Rを解析)',
            ],
        },
        {
            version: 'v0.3.2',
            date: '2026-02-06',
            highlights: [
                'ヘッダーにバージョン表示を追加',
                'プログラムのコピー機能',
                'WAV プレイヤーにインターバル再生モードを追加',
                'WAV プレイヤーのリピート/タイマー動作を修正',
                'ダークテーマの不具合修正・サーバ運用手順を README に追記',
            ],
        },
        {
            version: 'v0.3.0',
            date: '2026-01-06',
            highlights: [
                'WAV プレイヤー機能を追加',
                '停止タイマー機能',
                'WaveGenerator → SonicGenerator にリネーム',
            ],
        },
        {
            version: 'v0.2.0',
            date: '2025-12-02',
            highlights: [
                'UI デザイン刷新 — ダークテーマ・SVGアイコン・ツールバー',
                'Web Audio API によるブラウザ再生',
                'エクスポート時のファイル名指定・プログラム名のインライン編集',
                '再生コントロール改善 (ステージ移動・ステータス表示・バックエンド選択)',
            ],
        },
        {
            version: 'v0.1.1',
            date: '2025-11-18',
            highlights: [
                '初版 — 音波洗浄システム (リアルタイム波形可視化)',
                'tone / sweep トラック生成・ミックス・WAV エクスポート',
                'クロスプラットフォーム音声バックエンド (paplay / sounddevice)',
            ],
        },
    ],

    async init() {
        // /api/version から現在のバージョンを取得 (VERSION ファイルベース)
        try {
            const r = await fetch('/api/version');
            if (r.ok) {
                const data = await r.json();
                if (data.version) this.CURRENT = data.version;
            }
        } catch (e) { /* fallback to "unknown" */ }
        const btn = document.getElementById('btn-changelog');
        if (btn) btn.addEventListener('click', () => this.show());
        this._refreshDot();
    },

    _refreshDot() {
        const dot = document.getElementById('btn-changelog-dot');
        if (!dot) return;
        const seen = localStorage.getItem('changelog.lastSeen');
        dot.style.display = (seen !== this.CURRENT) ? '' : 'none';
    },

    show() {
        if (!this._modal) this._buildModal();
        this._modal.style.display = 'flex';
        localStorage.setItem('changelog.lastSeen', this.CURRENT);
        this._refreshDot();
    },

    _buildModal() {
        const wrap = document.createElement('div');
        wrap.id = 'changelog-overlay';
        wrap.style.cssText = `
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        `;

        const entriesHtml = this.ENTRIES.map((e, i) => {
            const isLatest = (i === 0);
            return `
                <div style="margin-bottom:14px; padding-bottom:12px; ${i < this.ENTRIES.length - 1 ? 'border-bottom:1px solid rgba(255,255,255,0.1);' : ''}">
                    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
                        <strong style="font-size:14px; color:${isLatest ? '#1abc9c' : '#e0e0e0'};">${e.version}</strong>
                        <span style="font-size:11px; color:#888;">${e.date}</span>
                    </div>
                    <ul style="margin:0; padding-left:18px; font-size:12px; color:#c0c0c0; line-height:1.7;">
                        ${e.highlights.map(h => `<li>${h}</li>`).join('')}
                    </ul>
                </div>
            `;
        }).join('');

        wrap.innerHTML = `
            <div style="background:#1a1a2e; border:1px solid rgba(255,255,255,0.12); border-radius:10px; box-shadow:0 8px 32px rgba(0,0,0,0.5); width:560px; max-width:92vw; max-height:80vh; display:flex; flex-direction:column; padding:18px; color:#e0e0e0;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                    <strong style="font-size:16px;">What's New</strong>
                    <button class="cl-close" style="background:none; border:none; font-size:22px; cursor:pointer; color:#888; padding:0 6px;">&times;</button>
                </div>
                <div style="overflow-y:auto; padding-right:4px;">${entriesHtml}</div>
            </div>
        `;
        document.body.appendChild(wrap);
        this._modal = wrap;

        wrap.addEventListener('mousedown', (e) => {
            if (e.target === wrap) wrap.style.display = 'none';
        });
        wrap.querySelector('.cl-close').addEventListener('click', () => {
            wrap.style.display = 'none';
        });
        document.addEventListener('keydown', (e) => {
            if (this._modal && this._modal.style.display === 'flex' && e.key === 'Escape') {
                this._modal.style.display = 'none';
            }
        });
    },
};

document.addEventListener('DOMContentLoaded', () => Changelog.init());
