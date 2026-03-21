import os
import json
import tweepy  # type: ignore
import requests  # type: ignore
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv  # type: ignore

base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

# X API 認証情報の取得
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

def send_slack_notification(message):
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})
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
    if data.get('image'):
        # 相対パスを絶対パスに変換
        img_path = os.path.join(base_dir, data['image'])
        if os.path.exists(img_path):
            media = client_v1.media_upload(filename=img_path)
            media_ids.append(media.media_id)

    last_tweet_id = None
    for i, content in enumerate(data['content']):
        if i == 0:
            response = client_v2.create_tweet(text=content, media_ids=media_ids if media_ids else None)
            last_tweet_id = response.data['id']
        else:
            response = client_v2.create_tweet(text=content, in_reply_to_tweet_id=last_tweet_id)
            last_tweet_id = response.data['id']
    return last_tweet_id

def main():
    json_path = os.path.join(base_dir, 'post_data.json')
    
    # 日本時間を取得
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    with open(json_path, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)

    updated = False
    
    for post in all_posts:
        if post.get('is_posted', False):
            continue

        # スケジュール時刻を比較 (YYYY-MM-DD HH:MM)
        post_datetime_str = f"{post['date']} {post['time']}"
        post_datetime = datetime.strptime(post_datetime_str, '%Y-%m-%d %H:%M').replace(tzinfo=jst)

        # 現在の時刻が、投稿予定時刻を過ぎているか？
        if now >= post_datetime:
            try:
                print(f"Executing post for {post_datetime_str}")
                post_tweet(post)
                
                # Slackに通知を送信
                msg = f"🟢 【IMA検定: X自動投稿完了】\n日時: {post['date']} {post['time']}\n内容: {post['content'][0][:50]}..."
                send_slack_notification(msg)
                
                # 投稿済みに変更
                post['is_posted'] = True
                updated = True
                # 今回の実行では1つだけ送信して終了（次回Actionに回す）
                break
                
            except Exception as e:
                err_msg = f"🔴 【IMA検定: X自動投稿エラー】\n日時: {post['date']} {post['time']}\nエラー内容: {e}"
                send_slack_notification(err_msg)
                print(f"Error: {e}")
                break

    # 投稿したらJSONを上書き保存
    if updated:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        print("Updated post_data.json with is_posted=True")

if __name__ == "__main__":
    if all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        main()
    else:
        print("Twitter API keys are not fully set in environment variables.")
