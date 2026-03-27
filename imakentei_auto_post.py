import os
import json
import tweepy  # type: ignore
import time
from datetime import datetime
from dotenv import load_dotenv  # type: ignore

# .env ファイルから環境変数を読み込む
load_dotenv()

# X API 認証情報の取得
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')

def get_twitter_conn_v1(api_key, api_secret, access_token, access_token_secret) -> tweepy.API:
    # メディアアップロード用の V1.1 認証
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    return tweepy.API(auth)

def get_twitter_conn_v2(api_key, api_secret, access_token, access_token_secret) -> tweepy.Client:
    # 投稿用の V2 認証
    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

def post_tweet(data):
    """
    指定されたデータを元にTweetを投稿する。
    画像がある場合は V1.1 でアップロード、投稿は V2 で行う。
    """
    client_v1 = get_twitter_conn_v1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    client_v2 = get_twitter_conn_v2(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)

    media_ids = []
    if data.get('image') and os.path.exists(data['image']):
        print(f"Uploading image: {data['image']}")
        media = client_v1.media_upload(filename=data['image'])
        media_ids.append(media.media_id)

    # スレッド投稿（複数投稿）
    last_tweet_id = None
    for i, content in enumerate(data['content']):
        if i == 0:
            # 最初の投稿（画像付き）
            response = client_v2.create_tweet(text=content, media_ids=media_ids if media_ids else None)
            last_tweet_id = response.data['id']
            print(f"Posted main tweet: {last_tweet_id}")
        else:
            # スレッド（返信）
            response = client_v2.create_tweet(text=content, in_reply_to_tweet_id=last_tweet_id)
            last_tweet_id = response.data['id']
            print(f"Posted thread reply: {last_tweet_id}")

def run_scheduler():
    """
    JSONを読み込んで、現在時刻に合う投稿があれば実行する
    """
    json_path = '/Users/kouichimatsumoto/Vault/Work/SNS・オウンドメディアコンテンツ運用/X_Algorithm/post_data.json'
    
    while True:
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        
        print(f"Checking schedule... {current_date} {current_time}")

        with open(json_path, 'r', encoding='utf-8') as f:
            all_posts = json.load(f)

        for post in all_posts:
            # 日付と時間が一致したら投稿
            if post['date'] == current_date and post['time'] == current_time:
                try:
                    print(f"Time to post! Date: {post['date']}, Time: {post['time']}")
                    post_tweet(post)
                except Exception as e:
                    print(f"Error posting: {e}")
                
        # 1分待機
        time.sleep(60)

if __name__ == "__main__":
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        print("Error: X API credentials not found in environment variables.")
    else:
        print("Starting imakentei X auto-poster...")
        run_scheduler()
