import os
import json
import tweepy  # type: ignore
import requests  # type: ignore
from datetime import datetime, timedelta
from dotenv import load_dotenv  # type: ignore

# .env ファイルから環境変数を読み込む
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# X API 認証情報の取得
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

def send_slack_notification(message):
    """
    Slackに通知を送信する
    """
    if not SLACK_WEBHOOK_URL:
        return
    
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Slack Notification Error: {e}")

def get_twitter_conn_v1(api_key, api_secret, access_token, access_token_secret):
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    return tweepy.API(auth)

def get_twitter_conn_v2(api_key, api_secret, access_token, access_token_secret):
    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

def post_tweet(data):
    client_v1 = get_twitter_conn_v1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    client_v2 = get_twitter_conn_v2(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)

    media_ids = []
    if data.get('image') and os.path.exists(data['image']):
        media = client_v1.media_upload(filename=data['image'])
        media_ids.append(media.media_id)

    last_tweet_id = None
    for i, content in enumerate(data['content']):  # type: ignore
        if i == 0:
            response = client_v2.create_tweet(text=content, media_ids=media_ids if media_ids else None)
            last_tweet_id = response.data['id']
        else:
            response = client_v2.create_tweet(text=content, in_reply_to_tweet_id=last_tweet_id)
            last_tweet_id = response.data['id']
    return last_tweet_id

def main():
    json_path = os.path.join(os.path.dirname(__file__), 'post_data.json')
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    
    # 念のため、1分前(sleep等でずれた場合)もチェック対象にする
    one_minute_ago = (now - timedelta(minutes=1)).strftime('%H:%M')

    with open(json_path, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)

    for post in all_posts:
        if post['date'] == current_date and (post['time'] == current_time or post['time'] == one_minute_ago):
            # すでに投稿済みかどうか（同じ時間に何度も投稿しないようにログをチェックする等の処理が望ましいが、簡易化のため1回だけ実行）
            # ここでは単純に投稿を実行
            try:
                print(f"Executing post for {current_date} {post['time']}")
                post_tweet(post)
                
                # Slackに通知を送信
                msg = f"【X投稿完了】\n日時: {post['date']} {post['time']}\n内容: {post['content'][0][:50]}..."
                send_slack_notification(msg)
                
                # 投稿の重複を防ぐための簡易フラグ（このセッションで一度だけ）として終了
                break
            except Exception as e:
                err_msg = f"【X投稿エラー】\n日時: {current_date} {post['time']}\nエラー内容: {e}"
                send_slack_notification(err_msg)
                print(f"Error: {e}")

if __name__ == "__main__":
    if all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        main()
