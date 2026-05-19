import os
import re
import json
import base64
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.async_api import async_playwright
import requests

# ── 設定 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
V3_DIR = Path(__file__).parent
POST_DATA_PATH = BASE_DIR / "post_data.json"
POST_HISTORY_PATH = BASE_DIR / "post_history.log"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
JST = timezone(timedelta(hours=9))

# Xアカウントのユーザーネーム（IDフォールバック取得に使用）
X_USERNAME = "imakentei"

# 投稿後のURL安定待機秒数
POST_WAIT_SEC = 10
# リプライ投稿間の待機秒数（連投制限対策）
REPLY_INTERVAL_SEC = 5


def write_post_history(status: str, scheduled_dt: str, tweet_num: int, total: int,
                       tweet_id: str | None, text: str):
    """投稿結果を post_history.log に1行追記する"""
    now_str = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
    url = f"https://x.com/{X_USERNAME}/status/{tweet_id}" if tweet_id else "URL取得失敗"
    preview = text[:45].replace('\n', ' ')
    line = (
        f"[{now_str}] {status}"
        f"  予定:{scheduled_dt}"
        f"  ツイート:{tweet_num}/{total}"
        f"  ID:{tweet_id or 'N/A'}"
        f"  {url}"
        f"  「{preview}…」\n"
    )
    with open(POST_HISTORY_PATH, 'a', encoding='utf-8') as f:
        f.write(line)
    print(line.strip())


def send_slack_notification(message):
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    except Exception as e:
        print(f"Slack通知エラー: {e}")


async def _build_context(playwright):
    """ブラウザコンテキストをstate.jsonから生成する"""
    state_path = V3_DIR / "state.json"
    state_b64 = os.environ.get("X_STATE_BASE64")
    if state_b64 and not state_path.exists():
        with open(state_path, "wb") as f:
            f.write(base64.b64decode(state_b64))

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        storage_state=str(state_path) if state_path.exists() else None,
        viewport={"width": 1280, "height": 800},
    )
    return browser, context


async def _get_latest_tweet_id(page, known_ids: set) -> str | None:
    """
    プロフィールページから known_ids に含まれない最新ツイートIDを返す。
    Intent URL投稿後は /home にリダイレクトされるためURL取得ができず、
    このフォールバックでリプライ連鎖用のIDを確保する。
    """
    await page.goto(
        f"https://x.com/{X_USERNAME}/with_replies",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    await asyncio.sleep(4)
    links = await page.locator(f'a[href*="/{X_USERNAME}/status/"]').all()
    ids = []
    for link in links:
        href = await link.get_attribute("href")
        m = re.search(r"/status/(\d+)", href)
        if m:
            ids.append(int(m.group(1)))
    new_ids = [i for i in ids if i not in known_ids]
    return str(max(new_ids)) if new_ids else None


async def _post_via_intent(page, text, in_reply_to_id=None, image_path=None, known_ids=None):
    """
    Intent URL方式でツイートを投稿し、投稿済みツイートのIDを返す。
    in_reply_to_id が指定された場合はリプライとして投稿する。
    投稿後URLからIDが取得できない場合はプロフィールページへフォールバックする。
    """
    import urllib.parse

    encoded = urllib.parse.quote(text)
    if in_reply_to_id:
        url = f"https://x.com/intent/tweet?in_reply_to={in_reply_to_id}&text={encoded}"
    else:
        url = f"https://x.com/intent/post?text={encoded}"

    print(f"[v3_playwright] アクセス中: {url[:80]}...")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    if "login" in page.url:
        raise RuntimeError("Xへのログインが必要です。state.jsonを更新してください。")

    # 画像アップロード（最初のツイートのみ）
    if image_path and image_path.exists():
        print(f"[v3_playwright] 画像アップロード中: {image_path.name}")
        async with page.expect_file_chooser() as fc_info:
            await page.locator('div[data-testid="fileInput"]').click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(image_path))
        await asyncio.sleep(5)

    # 投稿ボタンをクリック
    post_button = page.locator('button[data-testid="tweetButton"]').first
    await post_button.wait_for(state="visible", timeout=30000)
    await post_button.click()
    print("[v3_playwright] 投稿ボタンをクリックしました。")

    # 1. 投稿後URLからツイートIDを取得（成功すれば最速）
    await asyncio.sleep(POST_WAIT_SEC)
    match = re.search(r"/status/(\d+)", page.url)
    if match:
        tweet_id = match.group(1)
        print(f"[v3_playwright] ツイートID取得（URL）: {tweet_id}")
        return tweet_id

    # 2. URLから取得できなかった場合はプロフィールページへフォールバック
    print("[v3_playwright] URLからID取得できず → プロフィールページで確認中...")
    tweet_id = await _get_latest_tweet_id(page, known_ids or set())
    if tweet_id:
        print(f"[v3_playwright] ツイートID取得（プロフィール）: {tweet_id}")
        return tweet_id

    print("[v3_playwright] ツイートIDを取得できませんでした。")
    return None


async def post_to_x_playwright(post_item) -> list[str | None]:
    """
    Playwright でX（Twitter）に投稿する。
    スレッド（content が複数要素）の場合は全ツイートをリプライ連鎖で投稿する。
    各ツイートのIDを順番に格納したリストを返す（取得失敗時はNone）。
    """
    contents = post_item['content']
    image_path = BASE_DIR / post_item['image'] if post_item.get('image') else None
    total = len(contents)
    posted_ids: list[str | None] = []

    async with async_playwright() as p:
        browser, context = await _build_context(p)
        page = await context.new_page()

        try:
            last_id = None
            known_ids: set = set()
            for i, text in enumerate(contents):
                print(f"[v3_playwright] ツイート {i+1}/{total} を投稿中...")
                img = image_path if i == 0 else None  # 画像は1ツイート目のみ
                last_id = await _post_via_intent(
                    page, text,
                    in_reply_to_id=last_id,
                    image_path=img,
                    known_ids=known_ids,
                )
                posted_ids.append(last_id)
                if last_id:
                    known_ids.add(int(last_id))

                if last_id is None and i < total - 1:
                    print(f"[v3_playwright] スレッド中断: 残り{total - i - 1}件を投稿できませんでした。")
                    # 未投稿分はNoneで埋める
                    posted_ids.extend([None] * (total - i - 1))
                    break

                if i < total - 1:
                    await asyncio.sleep(REPLY_INTERVAL_SEC)

        except Exception as e:
            await page.screenshot(path=str(V3_DIR / "error_screenshot.png"))
            raise e
        finally:
            await context.close()
            await browser.close()

    return posted_ids


async def main():
    if not POST_DATA_PATH.exists():
        print(f"エラー: {POST_DATA_PATH} が見つかりません。")
        return

    now = datetime.now(JST)

    with open(POST_DATA_PATH, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)

    updated = False

    for post in all_posts:
        if post.get('is_posted', False):
            continue

        post_dt_str = f"{post['date']} {post['time']}"
        post_dt = datetime.strptime(post_dt_str, '%Y-%m-%d %H:%M').replace(tzinfo=JST)

        # 24時間以上過去の未投稿は投稿済み扱いにしてスキップ
        if now > post_dt + timedelta(days=1):
            print(f"[v3_playwright] 期限切れスキップ: {post_dt_str}")
            post['is_posted'] = True
            updated = True
            continue

        if now >= post_dt:
            total = len(post['content'])
            print(f"[v3_playwright] {now.strftime('%Y-%m-%d %H:%M:%S')} 投稿実行: {post_dt_str}（{total}件）")
            try:
                posted_ids = await post_to_x_playwright(post)

                # ツイートごとに履歴ログへ記録
                for i, (text, tid) in enumerate(zip(post['content'], posted_ids), 1):
                    status = "✅ POSTED " if tid else "⚠️ ID_MISS"
                    write_post_history(status, post_dt_str, i, total, tid, text)

                msg = (
                    f"🔵 【IMA検定: X自動投稿完了】\n"
                    f"日時: {post['date']} {post['time']}\n"
                    f"ツイート数: {total}件\n"
                    f"冒頭: {post['content'][0][:50]}..."
                )
                send_slack_notification(msg)

                post['is_posted'] = True
                updated = True
                break  # 1回につき1投稿（スレッド単位）

            except Exception as e:
                write_post_history("❌ ERROR  ", post_dt_str, 0, total, None, str(e))
                err_msg = (
                    f"🔴 【IMA検定: X自動投稿エラー】\n"
                    f"日時: {post['date']} {post['time']}\n"
                    f"エラー: {e}"
                )
                send_slack_notification(err_msg)
                print(f"エラー: {e}")
                break

    if updated:
        with open(POST_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        print("[v3_playwright] post_data.json を更新しました。")


if __name__ == "__main__":
    asyncio.run(main())
