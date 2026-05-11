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
    Playwright を使用してブラウザ上で X に投稿する (Intent URL 方式)。
    """
    import urllib.parse
    
    # 投稿内容のエンコード
    content = post_item['content'][0]
    encoded_text = urllib.parse.quote(content)
    intent_url = f"https://x.com/intent/post?text={encoded_text}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # ... (中略: state 読み込み部分は維持)
        state_path = V3_DIR / "state.json"
        import os
        import base64
        state_b64 = os.environ.get("X_STATE_BASE64")
        if state_b64 and not state_path.exists():
            with open(state_path, "wb") as f:
                f.write(base64.b64decode(state_b64))

        context = await browser.new_context(
            storage_state=str(state_path) if state_path.exists() else None,
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        try:
            print(f"[v3_playwright] Intent URL にアクセス中: {intent_url[:50]}...")
            await page.goto(intent_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            if "login" in page.url:
                raise RuntimeError("X へのログインが必要です。")

            # 投稿ボタンを待機
            post_button = page.locator('button[data-testid="tweetButton"]').first
            await post_button.wait_for(state="visible", timeout=30000)
            
            # 画像のアップロード
            if post_item.get('image'):
                img_path = BASE_DIR / post_item['image']
                if img_path.exists():
                    print(f"[v3_playwright] 画像をアップロード中: {img_path.name}")
                    async with page.expect_file_chooser() as fc_info:
                        await page.locator('div[data-testid="fileInput"]').click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(img_path))
                    await asyncio.sleep(5)

            # 投稿
            await post_button.click()
            print("[v3_playwright] 投稿ボタンをクリックしました。")
            await asyncio.sleep(10)

        except Exception as e:
            await page.screenshot(path=str(V3_DIR / "error_screenshot.png"))
            raise e
        finally:
            await context.close()
            await browser.close()

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

        # 過去すぎるデータ（24時間以上前）はスキップ
        if now > post_datetime + timedelta(days=1):
            print(f"[v3_playwright] 過去データのためスキップします: {post_datetime_str}")
            post['is_posted'] = True # 投稿済み扱いにして滞留を防ぐ
            updated = True
            continue

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
