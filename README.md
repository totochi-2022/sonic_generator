# Sonic Generator

音波洗浄システム - FastAPI ベースの音波生成・再生アプリケーション

## ローカル起動

```bash
# 通常起動（デフォルト: ポート8000）
python app.py

# ポート指定
python app.py --port 8001

# uvicornで起動
uvicorn app:app --host 0.0.0.0 --port 8001
```

### オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--host` | 0.0.0.0 | ホストアドレス |
| `--port` | 8000 | ポート番号 |
| `--backend` | paplay | オーディオバックエンド (paplay/sounddevice) |

## サーバー運用 (192.168.2.180)

### サービス設定

- **ユーザー**: srvadmin
- **ポート**: 3100
- **ディレクトリ**: `/home/srvadmin/sonic_generator`
- **サービス名**: sonic-generator

### systemd サービスファイル

`/etc/systemd/system/sonic-generator.service`:

```ini
[Unit]
Description=SonicGenerator
After=network.target

[Service]
Type=simple
User=srvadmin
WorkingDirectory=/home/srvadmin/sonic_generator
ExecStart=/home/srvadmin/sonic_generator/venv/bin/python app.py --host 0.0.0.0 --port 3100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 操作コマンド

```bash
# 状態確認
sudo systemctl status sonic-generator

# 再起動
sudo systemctl restart sonic-generator

# 停止
sudo systemctl stop sonic-generator

# 起動
sudo systemctl start sonic-generator

# 自動起動有効化
sudo systemctl enable sonic-generator

# ログ確認
sudo journalctl -u sonic-generator -f
```

### アクセスURL

- http://192.168.2.180:3100
