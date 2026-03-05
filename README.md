# Claude Usage Monitor

Claude.aiの使用量をリアルタイムで確認できるWindowsデスクトップアプリです。  
Chrome拡張機能は不要で、単体で動作します。

![screenshot](docs/screenshot.png)

---

## 機能

- **プラン使用制限** の可視化（現在のセッション・週間制限）
- **追加使用量** の表示（使用額・上限・残高）
- **1分ごとの自動更新**
- **手動更新ボタン**（↻）
- **システムトレイ常駐**（右クリックメニューあり）
- アカウント切り替え・ログアウト（設定画面 ⚙）

---

## 必要環境

- Windows 10 / 11
- Python 3.8 以上
- インターネット接続

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/YOUR_USERNAME/claude-usage-monitor.git
cd claude-usage-monitor/app
```

### 2. 起動

**通常起動（CMDウィンドウなし）**
```
start.vbs をダブルクリック
```

**デバッグ起動（エラー確認用）**
```
start_debug.bat をダブルクリック
```

初回起動時に自動で以下が実行されます：
1. 依存ライブラリのインストール（`playwright`, `pystray`, `Pillow`）
2. Chromiumブラウザのダウンロード（約100MB・初回のみ）

---

## 使い方

### 初回ログイン

1. `start.vbs` を起動するとブラウザが自動で開きます
2. Google またはメールアドレスで claude.ai にログイン
3. ログイン完了後、アプリの **「✓ ログイン完了」** ボタンを押します
4. 使用量が自動で表示されます

> ログイン情報は `~/.claude-monitor/profile/` にローカル保存されます。  
> 次回以降はブラウザが表示されずにバックグラウンドで起動します。

### 日常的な使い方

- タスクバーのトレイアイコンをダブルクリックで表示/非表示
- `↻` ボタンで即時更新
- `⚙` ボタンで設定画面（アカウント切り替え・ログアウト）

---

## 仕組み

```
起動
 └─ Playwright（Chromiumブラウザ）
      └─ claude.ai/settings/usage にアクセス
           ├─ ログイン済み → バックグラウンドで1分ごとに自動取得
           └─ 未ログイン  → ブラウザウィンドウを表示してログイン
```

- バックグラウンド動作時はブラウザウィンドウを画面外（`-32000, -32000`）に配置するため、ユーザーには見えません
- ヘッドレスモードは使用していません（claude.aiのボット検知を回避するため）
- 取得したデータはローカルにのみ保持し、外部への送信は一切行いません

---

## ファイル構成

```
app/
├── app.py          # UIメイン（tkinter）
├── scraper.py      # Playwrightスクレイパー
├── requirements.txt
├── start.vbs       # CMDなし起動（通常用）
└── start_debug.bat # デバッグ起動
```

---

## 依存ライブラリ

| ライブラリ | 用途 |
|-----------|------|
| [Playwright](https://playwright.dev/python/) | ブラウザ自動化・スクレイピング |
| [pystray](https://github.com/moses-palmer/pystray) | システムトレイアイコン |
| [Pillow](https://pillow.readthedocs.io/) | トレイアイコン画像生成 |

---

## ⚠️ 注意事項

- このアプリは **個人利用を目的** としています
- claude.ai のDOMをスクレイピングするため、Anthropicがサイト構造を変更した場合に動作しなくなる可能性があります
- Anthropic の[利用規約](https://www.anthropic.com/legal/consumer-terms)をご確認の上、**自己責任でご利用ください**
- ログイン情報（Cookieなど）はお使いのPC内にのみ保存されます

---

## トラブルシューティング

**データが取得できない（「データ解析中...」のまま）**  
→ `↻` ボタンを押して再試行してください

**ログインしたのに認識されない**  
→ ブラウザでログイン後、アプリの「✓ ログイン完了」ボタンを押してください

**プロファイルをリセットしたい**  
→ `%USERPROFILE%\.claude-monitor\profile\` フォルダを削除して再起動してください

**エラーの詳細を確認したい**  
→ `start_debug.bat` で起動するとCMDにログが表示されます

---

## License

MIT License
