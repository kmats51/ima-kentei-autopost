import os
import json
import tweepy
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
script_dir = '/Users/kouichimatsumoto/Vault/Work/SNS・オウンドメディアコンテンツ運用/X_Algorithm/'
load_dotenv(os.path.join(script_dir, '.env'))

# X API 認証情報の取得
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

def get_twitter_client():
    return tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET
    )

def send_to_slack(message):
    if not SLACK_WEBHOOK_URL:
        return
    payload = {"text": message}
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload).raise_for_status()
    except:
        pass

def main():
    config_path = os.path.join(script_dir, 'targets.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    target_handles = config.get("target_handles", [])
    keywords = config.get("keywords", ["IMA検定"])
    client = get_twitter_client()

    # テスト期間: 2026-03-16 00:00:00 UTC 〜 2026-03-21 00:00:00 UTC
    start_time = "2026-03-16T00:00:00Z"
    end_time = "2026-03-21T00:00:00Z"

    full_report = f"🧪 *IMA検定 X投稿監視テストレポート (期間指定)*\n"
    full_report += f"対象期間: 2026/03/16 〜 2026/03/20\n\n"

    for handle in target_handles:
        print(f"Checking @{handle}...")
        try:
            user = client.get_user(username=handle)
            if not user or not user.data:
                full_report += f"➖ *@ {handle}* (ユーザーが見つかりません)\n"
                continue
            
            tweets = client.get_users_tweets(id=user.data.id, start_time=start_time, end_time=end_time, tweet_fields=['created_at', 'text'])
            
            matching = []
            if tweets.data:
                for tweet in tweets.data:
                    if any(kw.lower() in tweet.text.lower() for kw in keywords):
                        matching.append(tweet)
            
            if matching:
                full_report += f"✅ *@ {handle}* ({len(matching)}件ヒット)\n"
                for t in matching:
                    full_report += f"• {t.text[:50]}...\n"
            else:
                full_report += f"➖ *@ {handle}* (該当投稿なし)\n"
        except Exception as e:
            full_report += f"⚠️ *@ {handle}* (APIエラー: {str(e)[:30]})\n"

    send_to_slack(full_report)
    print(full_report)

if __name__ == "__main__":
    main()
