# IMA検定 X投稿監視ツール

## 概要
対象の X アカウントを毎週月曜日に自動チェックし、「IMA検定」を含む投稿を Slack に通知するツールです。  
GitHub Actions で動作するため、**PC の起動は不要です。**

---

## ファイル構成

```
.
├── .github/
│   └── workflows/
│       └── ima_kentei_checker.yml  ← GitHub Actions スケジュール設定
├── 2026-03-21_ima_kentei_checker.py  ← メイン監視スクリプト
├── targets.json                      ← 監視対象アカウント・キーワード設定
├── requirements.txt                  ← Python ライブラリ
└── README.md                         ← このファイル
```

---

## セットアップ手順

### 1. GitHub リポジトリを作成
1. https://github.com/new を開く
2. リポジトリ名を入力（例: `ima-kentei-checker`）
3. **Private（非公開）** を選択（APIキーなどを含むため）
4. 「Create repository」をクリック

### 2. ファイルをアップロード
```bash
# このフォルダ内で実行
cd /Users/kouichimatsumoto/Vault/Work/SNS・オウンドメディアコンテンツ運用/X_Algorithm/

git init
git add 2026-03-21_ima_kentei_checker.py targets.json requirements.txt .github/
git commit -m "Initial commit: IMA検定 X投稿監視ツール"
git remote add origin https://github.com/[あなたのユーザー名]/ima-kentei-checker.git
git push -u origin main
```

### 3. Slack Webhook URL を GitHub Secrets に登録
1. リポジトリの **Settings** → **Secrets and variables** → **Actions** を開く
2. **「New repository secret」** をクリック
3. 以下を入力：
   - **Name**: `SLACK_WEBHOOK_URL`
   - **Secret**: `.env` に記載している Webhook URL をそのまま貼り付け
4. 「Add secret」をクリック

### 4. 動作確認（手動実行）
1. リポジトリの **Actions** タブを開く
2. **「IMA検定 X投稿監視（週次）」** を選択
3. **「Run workflow」** → **「Run workflow」** をクリック
4. 数分後に Slack に通知が届けば成功

---

## 自動実行スケジュール

| タイミング | 説明 |
|:---|:---|
| **毎週月曜日 08:00 JST** | 自動実行（PC不要） |
| いつでも | GitHub の Actions タブから手動実行可能 |

---

## 監視対象の変更方法

`targets.json` を編集して Git にプッシュするだけです。

```json
{
  "target_handles": [
    "haccihacci3",
    "y_document",
    "NaphonNet",
    "yumeco_smile",
    "kabbochan11"
  ],
  "keywords": [
    "IMA検定"
  ]
}
```

---

## 使用ライブラリ
- `requests` - HTTP リクエスト
- `python-dotenv` - 環境変数管理（ローカル実行時のみ使用）

※ X API 不要。Nitter（X のオープンフロントエンド）の RSS フィードを使用して投稿を取得。
