"""
IMA検定 X投稿監視スクリプト
-------------------------------
対象アカウントの X タイムラインを Nitter RSS フィード経由で取得し、
過去 7 日以内に「IMA検定」を含む投稿（ハッシュタグあり・なし両対応）があれば
検出して Slack に通知する。

X API 不要（Freeプランでも動作）。
"""

import os
import re
import json
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

# スクリプトと同じディレクトリの .env を読み込む
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, '.env'))

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

# 使用する Nitter インスタンス（フォールバック付き）
NITTER_INSTANCES = [
    'https://nitter.net',
    'https://nitter.privacydev.net',
    'https://nitter.poast.org',
    'https://nitter.1d4.us',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def get_working_nitter():
    """動作する Nitter インスタンスを返す"""
    for base in NITTER_INSTANCES:
        try:
            r = requests.get(f'{base}/x', headers=HEADERS, timeout=6)
            if r.status_code in (200, 302, 404):
                return base
        except Exception:
            continue
    return None

def fetch_user_tweets_rss(nitter_base, handle, keywords, start_time):
    """
    Nitter RSS フィードでユーザーのタイムラインを取得し、
    指定キーワードリストのいずれかを含む・指定期間内の投稿を返す。
    """
    url = f'{nitter_base}/{handle}/rss'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        channel = root.find('channel')
        if channel is None:
            return [], None

        matched = []
        for item in channel.findall('item'):
            # 投稿テキスト（HTML タグを除去）
            title     = item.findtext('title', '')
            desc_html = item.findtext('description', '')
            desc_text = re.sub(r'<[^>]+>', '', desc_html).strip()
            full_text = title + '\n' + desc_text

            # X の投稿 URL（nitter → twitter.com に変換）
            nitter_link = item.findtext('link', '')
            tweet_url = nitter_link.replace(nitter_base, 'https://x.com').replace('#m', '')

            # 投稿日時
            pub_raw = item.findtext('pubDate', '')
            try:
                pub_dt = parsedate_to_datetime(pub_raw)
            except Exception:
                continue

            # 期間チェック（start_time より新しい投稿のみ）
            if pub_dt < start_time:
                continue

            # キーワードチェック（リスト内のいずれかがマッチすれば OK）
            if any(kw.lower() in full_text.lower() for kw in keywords):
                jst = timezone(timedelta(hours=9))
                matched.append({
                    'text': full_text.strip(),
                    'url': tweet_url,
                    'published_at': pub_dt.astimezone(jst).strftime('%Y-%m-%d %H:%M'),
                })

        return matched, None

    except ET.ParseError as e:
        return [], f'RSS パースエラー: {e}'
    except Exception as e:
        return [], f'取得エラー: {e}'

def send_to_slack(message):
    """Slack Incoming Webhook で通知を送信"""
    if not SLACK_WEBHOOK_URL:
        print('⚠️  Slack Webhook URL が設定されていません。')
        return
    try:
        res = requests.post(SLACK_WEBHOOK_URL, json={'text': message}, timeout=10)
        res.raise_for_status()
        print('Slack 通知を送信しました。')
    except Exception as e:
        print(f'Slack 通知に失敗しました: {e}')

def main():
    # 設定ファイルを読み込む
    config_path = os.path.join(script_dir, 'targets.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    target_handles = config.get('target_handles', [])
    keywords       = config.get('keywords', ['IMA検定'])  # targets.json から読み込む

    # 対象期間（日本時間 → UTC に変換）
    jst = timezone(timedelta(hours=9))
    now_jst      = datetime.now(jst)
    one_week_ago = now_jst - timedelta(days=7)
    start_time   = one_week_ago.astimezone(timezone.utc)

    # 動作する Nitter を選択
    nitter_base = get_working_nitter()
    if not nitter_base:
        print('❌ 利用可能な Nitter インスタンスが見つかりません。')
        return
    print(f'🌐 使用 Nitter: {nitter_base}')

    # ---- チェック実行 ----
    all_found   = {}  # handle -> list of tweet dicts
    found_count = 0

    for handle in target_handles:
        print(f'  Checking @{handle}...')
        tweets, err = fetch_user_tweets_rss(nitter_base, handle, keywords, start_time)
        if err:
            print(f'    ⚠️  {err}')
            all_found[handle] = []
        else:
            all_found[handle] = tweets
            if tweets:
                found_count += len(tweets)
                for t in tweets:
                    print(f'    ✅ {t["published_at"]} {t["url"]}')
            else:
                print(f'    ➖ 該当なし')

    # ---- Slack メッセージ組み立て ----
    report  = f'📊 *IMA検定 X投稿監視レポート（先週分）*\n'
    report += f'集計日時: {now_jst.strftime("%Y-%m-%d %H:%M")}\n'
    report += f'対象期間: {one_week_ago.strftime("%m/%d (%a)")} 〜 {(now_jst - timedelta(days=1)).strftime("%m/%d (%a)")}\n'
    report += f'検索キーワード: `{" / ".join(keywords)}`\n\n'

    for handle in target_handles:
        tweets = all_found.get(handle, [])
        if tweets:
            report += f'✅ *@{handle}* — {len(tweets)}件の投稿を検出\n'
            for t in tweets:
                snippet = t['text'].replace('\n', ' ')[:60]
                report += f'  • [{t["published_at"]}] {snippet}...\n'
                report += f'    🔗 <{t["url"]}>\n'
        else:
            report += f'➖ *@{handle}* — 投稿なし\n'

    report += f'\n---\n*合計: {len(target_handles)} アカウント中 {found_count} 件ヒット*'

    print('\n--- Summary Report ---')
    print(report)

    # Slack に送信
    send_to_slack(report)

    # 結果を JSON に保存（履歴用）
    log_path = os.path.join(script_dir, 'monitor_results.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump({
            'checked_at': now_jst.strftime('%Y-%m-%d %H:%M:%S'),
            'method':     'nitter_rss',
            'keywords':   keywords,
            'results':    all_found,
        }, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
