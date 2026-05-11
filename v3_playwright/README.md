# IMA検定 X自動投稿システム v3 (Playwright版)

X API の制限（402 Payment Required）を回避するため、ブラウザ自動操作（Playwright）を使用して投稿を行う仕組みです。
既存の API ベースの仕組みとは独立して動作します。

## ディレクトリ構成
- `ima_playwright_poster.py`: 自動投稿のメインスクリプト
- `x_login_helper.py`: 初回ログイン・セッション保存用ヘルパー
- `state.json`: ブラウザのログイン状態（クッキー等）を保存するファイル（軽量）
- `requirements.txt`: 必要なライブラリ

## セットアップ手順

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. X へのログイン（セッション作成）
以下のコマンドを実行し、立ち上がったブラウザで X にログインしてください。
完了後、ブラウザを閉じると `state.json` にログイン情報が保存されます。
```bash
python x_login_helper.py
```

### 3. 自動投稿のテスト実行
`post_data.json` に有効な（今日の日付の）データがあることを確認し、実行します。
```bash
python ima_playwright_poster.py
```

## GitHub Actions での運用手順

1. **Base64 文字列の生成**
   ローカルで `state.json` を生成した後、以下のコマンドで Base64 文字列を取得します。
   ```bash
   cat state.json | base64 | pbcopy  # Macの場合
   ```

2. **GitHub Secrets への登録**
   リポジトリの `Settings > Secrets and variables > Actions` にて、新しい Secret を登録します。
   - Name: `X_STATE_BASE64`
   - Secret: 手順1でコピーした文字列

3. **ワークフローの確認**
   `.github/workflows/post_v3.yml` が自動的に 1時間ごとにチェックを行います。手動で実行したい場合は GitHub の Actions タブから `Run workflow` をクリックしてください。
