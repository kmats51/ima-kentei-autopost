import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

USER_DATA_DIR = Path(__file__).parent / "user_data"

async def setup_login():
    """
    ブラウザを起動して手動ログインを待機し、クッキー情報を state.json に保存する。
    """
    async with async_playwright() as p:
        print("ブラウザを起動します。X(Twitter)にログインしてください。")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        
        page = await context.new_page()
        await page.goto("https://x.com/login")
        
        print("ログイン完了後、このスクリプトを終了（Ctrl+C）またはブラウザを閉じてください。")
        
        try:
            while True:
                await asyncio.sleep(1)
                if page.is_closed():
                    break
        except KeyboardInterrupt:
            pass
        finally:
            # ログイン状態を保存
            await context.storage_state(path=str(Path(__file__).parent / "state.json"))
            print(f"ログイン情報を state.json に保存しました。")
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(setup_login())
