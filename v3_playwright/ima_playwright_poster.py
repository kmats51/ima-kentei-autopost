import os
import json
import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.async_api import async_playwright
import requests

# ── 設定 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
V3_DIR = Path(__file__).parent
POST_DATA_PATH = BASE_DIR / "post_data.json"
USER_DATA_DIR = V3_DIR / "user_data"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# 日本時間 (JST)
JST = timezone(timedelta(hours=9))

def send_slack_notification(message):
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    except Exception as e:
        print(f"Slack Notification Error: {e}")

async def post_to_x_playwright(post_item):
    """
    Playwright を使用してブラウザ上で X に投稿する。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # ログイン情報をファイルまたは環境変数から読み込む
        state_path = V3_DIR / "state.json"
        
        # GitHub Actions 等の環境変数に Base64 がある場合は書き出し
        import os
        import base64
        state_b64 = os.environ.get("X_STATE_BASE64")
        if state_b64 and not state_path.exists():
            print("環境変数から state.json を復元します...")
            with open(state_path, "wb") as f:
                f.write(base64.b64decode(state_b64))

        if state_path.exists():
            context = await browser.new_context(
                storage_state=str(state_path),
                viewport={"width": 1280, "height": 800}
            )
        else:
            print("警告: ログイン情報 (state.json) が見つかりません。")
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
        
        page = await context.new_page()
        
        try:
            print("[v3_playwright] X にアクセス中...")
            await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
            
            # ページが読み込まれるまで少し待機
            await asyncio.sleep(5)
            
            # ログインチェック
            if "login" in page.url:
                raise RuntimeError("X へのログインが必要です。user_data 内にセッションがありません。")

            # 投稿内容の入力
            # スレッド対応（現在は1件目のみ対応、必要に応じて拡張）
            content = post_item['content'][0]
            
            # 投稿エリア（エディタ）を探して入力
            editor = page.locator('div[data-testid="tweetTextarea_0"]').first
            await editor.wait_for(timeout=30000)
            await editor.click()
            await editor.type(content, delay=50)  # 1文字ずつタイピングして入力を認識させる
            await asyncio.sleep(2)  # 入力後の反映待ち
            
            # 画像のアップロード
            if post_item.get('image'):
                img_path = BASE_DIR / post_item['image']
                if img_path.exists():
                    print(f"[v3_playwright] 画像をアップロード中: {img_path.name}")
                    # ファイル選択用の input を探す
                    async with page.expect_file_chooser() as fc_info:
                        await page.locator('div[data-testid="fileInput"]').click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(img_path))
                    # アップロード完了を少し待つ
                    await asyncio.sleep(5)
                else:
                    print(f"[v3_playwright] 警告: 画像が見つかりません: {img_path}")

            # 他のポップアップ（アップグレード勧誘など）を消すために一度 Escape を押す
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

            # 投稿ボタンをクリック
            post_button = page.locator('[data-testid*="tweetButton"]').first
            await post_button.wait_for(state="visible", timeout=10000)
            
            await post_button.click(force=True)
            print("[v3_playwright] 投稿ボタンを強制クリックしました。")
            # 投稿完了を待機
            await asyncio.sleep(10)

        except Exception as e:
            # エラー時にスクリーンショットを撮る（デバッグ用）
            await page.screenshot(path=str(V3_DIR / "error_screenshot.png"))
            raise e
        finally:
            await context.close()

async def main():
    if not POST_DATA_PATH.exists():
        print(f"Error: {POST_DATA_PATH} が見つかりません。")
        return

    now = datetime.now(JST)
    print(f"[v3_playwright] {now.strftime('%Y-%m-%d %H:%M:%S')} 実行開始")

    with open(POST_DATA_PATH, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)

    updated = False
    
    for post in all_posts:
        if post.get('is_posted', False):
            continue

        # スケジュール時刻を比較
        post_datetime_str = f"{post['date']} {post['time']}"
        post_datetime = datetime.strptime(post_datetime_str, '%Y-%m-%d %H:%M').replace(tzinfo=JST)

        if now >= post_datetime:
            try:
                print(f"[v3_playwright] 投稿を実行します: {post_datetime_str}")
                
                # Playwright で投稿実行
                await post_to_x_playwright(post)
                
                # Slackに通知
                msg = f"🔵 【IMA検定: X自動投稿(v3)完了】\n日時: {post['date']} {post['time']}\n方式: Playwright (Browser Automation)\n内容: {post['content'][0][:50]}..."
                send_slack_notification(msg)
                
                # 投稿済みに変更
                post['is_posted'] = True
                updated = True
                break # 1回につき1件投稿
                
            except Exception as e:
                err_msg = f"🔴 【IMA検定: X自動投稿(v3)エラー】\n日時: {post['date']} {post['time']}\nエラー内容: {e}"
                send_slack_notification(err_msg)
                print(f"Error: {e}")
                break

    # 投稿したらJSONを上書き保存
    if updated:
        with open(POST_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        print("[v3_playwright] post_data.json を更新しました。")

if __name__ == "__main__":
    asyncio.run(main())
