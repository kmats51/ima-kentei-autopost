"""
X投稿自動生成スクリプト

使い方:
  python3 generate_posts.py --csv path/to/analytics.csv
  python3 generate_posts.py --csv path/to/analytics.csv --count 4 --start 2026-05-26

前提条件:
  .env ファイルに GEMINI_API_KEY が設定されていること
"""

import os
import csv
import json
import re
import argparse
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFT_MD_FILE = os.path.join(BASE_DIR, 'draft_posts.md')
DRAFT_JSON_FILE = os.path.join(BASE_DIR, 'draft_posts.json')

# 広告投稿の識別パターン（分析から除外）
AD_PATTERNS = [
    'Webマーケターの\n98%が持っていない',
    'IMA検定のエントリーを検討している方へ',
    'AIエージェント9種を手に入れた人の',
]

ALGORITHM_SUMMARY = """
## Xアルゴリズム スコアリング重み

| アクション | スコア |
|---|---|
| 著者からの返信をもらったリプライ | +75.0（全施策中最高） |
| リプライ（返信） | +13.5 |
| プロフィールクリック＋いいね/リプライ | +12.0 |
| 会話クリック（詳細を見る） | +11.0 |
| 会話クリック＋2分以上滞在 | +10.0 |
| リツイート（Repost） | +1.0 |
| いいね（Like） | +0.5 |
| ネガティブ反応（ブロック・ミュート等） | -74.0 |
| スパム報告（Report） | -369.0 |

## 投稿最適化チェックリスト

1. 著者が積極的にリプライ返信 → スコア最大化（+75.0/件）
2. 末尾に問いかけを入れてリプライ誘発 → +13.5
3. プロフィール誘導の一行を追加 → +12.0
4. スレッドで続きを読みたくなる構成 → +11.0
5. 画像を含める（拡大タップ誘発） → P(photo_expand)加点
6. URLは本文に入れず自己リプライへ移動 → スパム判定ペナルティ回避
7. 問いかけあり投稿は問いかけなし投稿の約5倍のIMP実績あり
"""

IMA_BRAND_CONTEXT = """
## IMA検定 ブランドコンテキスト

**事業概要**
- 名称: IMA検定（インターネットマーケティング検定）
- URL: https://ima-kentei.jp
- 対象: Webマーケター・デジタルマーケター
- 特徴: AIエージェント9種配布・プロ添削・実務スキル習得
- 価格: Standard 24,970円 / Professional（上位資格）

**ブランドボイス**
- プロフェッショナルだが親しみやすい
- 実務に直結する具体的な情報提供
- 「あなたは今どうですか？」という当事者感を引き出す
- AI×マーケティングの掛け合わせを軸にする

**効果実績のあるテーマ（過去データより）**
- ChatGPT・AIの使い方の失敗パターン（スレッド型で高エンゲージメント）
- 「AIを使っている」と「成果を出している」の差
- マーケターの実務格差・スキル差の可視化
- Google広告・GA4の具体的な改善手法
- 選択肢型アンケート投稿（最もリプライを集めやすい）
- 「保存推奨📌」「スレッド🧵」形式の図解投稿

**禁止事項**
- 本文にURLを含める（IMPペナルティ -80%以上）
- 過度な宣伝・押し売りトーン
- 根拠のない数値の使用
"""


def load_env():
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        print("❌ エラー: GEMINI_API_KEY が .env に設定されていません。")
        print("   .env ファイルに以下を追加してください:")
        print("   GEMINI_API_KEY=AIza...")
        exit(1)
    return key


def analyze_csv(csv_path):
    """X Analytics CSVを分析してパフォーマンスサマリーを返す"""
    posts = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get('Tweet text', '').strip()
            if not text:
                continue
            # 広告投稿を除外
            if any(p in text for p in AD_PATTERNS):
                continue
            try:
                imp = int(row.get('impressions', 0) or 0)
                eng_rate_str = row.get('engagement rate', '0').replace('%', '').strip()
                eng_rate = float(eng_rate_str or 0)
                replies = int(row.get('replies', 0) or 0)
                likes = int(row.get('likes', 0) or 0)
                retweets = int(row.get('retweets', 0) or 0)
                profile_clicks = int(row.get('profile clicks', 0) or 0)
                url_clicks = int(row.get('url clicks', 0) or 0)
            except (ValueError, KeyError):
                continue

            posts.append({
                'text': text,
                'date': row.get('time', ''),
                'imp': imp,
                'eng_rate': eng_rate,
                'replies': replies,
                'likes': likes,
                'retweets': retweets,
                'profile_clicks': profile_clicks,
                'url_clicks': url_clicks,
                'has_question': '？' in text or '?' in text,
                'has_url': 'http' in text,
                'is_thread': bool(re.search(r'\(1/', text) or '🧵' in text),
            })

    if not posts:
        return None

    n = len(posts)
    avg_imp = sum(p['imp'] for p in posts) / n
    avg_eng = sum(p['eng_rate'] for p in posts) / n
    total_replies = sum(p['replies'] for p in posts)
    total_profile = sum(p['profile_clicks'] for p in posts)

    q_posts = [p for p in posts if p['has_question']]
    no_q_posts = [p for p in posts if not p['has_question']]
    url_posts = [p for p in posts if p['has_url']]
    no_url_posts = [p for p in posts if not p['has_url']]
    thread_posts = [p for p in posts if p['is_thread']]

    q_avg = sum(p['imp'] for p in q_posts) / len(q_posts) if q_posts else 0
    no_q_avg = sum(p['imp'] for p in no_q_posts) / len(no_q_posts) if no_q_posts else 1
    url_avg = sum(p['imp'] for p in url_posts) / len(url_posts) if url_posts else 0
    no_url_avg = sum(p['imp'] for p in no_url_posts) / len(no_url_posts) if no_url_posts else 1

    top5 = sorted(posts, key=lambda p: p['eng_rate'], reverse=True)[:5]

    return {
        'total': n,
        'avg_imp': round(avg_imp),
        'avg_eng': round(avg_eng, 2),
        'total_replies': total_replies,
        'total_profile': total_profile,
        'q_count': len(q_posts),
        'q_avg_imp': round(q_avg),
        'no_q_avg_imp': round(no_q_avg),
        'url_count': len(url_posts),
        'url_avg_imp': round(url_avg),
        'no_url_avg_imp': round(no_url_avg),
        'thread_count': len(thread_posts),
        'top5': top5,
    }


def build_schedule(start_str, count):
    """投稿スケジュールを生成（平日優先・48時間以上の間隔）"""
    jst = timezone(timedelta(hours=9))

    if start_str:
        base = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=jst, hour=7, minute=0)
    else:
        today = datetime.now(jst)
        days_ahead = 7 - today.weekday()  # 次の月曜日
        if days_ahead == 7:
            days_ahead = 7
        base = today + timedelta(days=days_ahead)
        base = base.replace(hour=7, minute=0, second=0, microsecond=0)

    slots = []
    current = base
    last_slot = None

    while len(slots) < count:
        weekday = current.weekday()
        if weekday < 5:  # 月〜金
            for hour, minute in [(7, 0), (12, 0)]:
                if len(slots) >= count:
                    break
                candidate = current.replace(hour=hour, minute=minute, second=0)
                if last_slot is None or (candidate - last_slot).total_seconds() >= 48 * 3600:
                    slots.append(candidate)
                    last_slot = candidate
        current += timedelta(days=1)

    return [(s.strftime('%Y-%m-%d'), s.strftime('%H:%M')) for s in slots]


def build_prompt(analysis, schedule, deadline):
    """Claude APIへのプロンプトを組み立てる"""
    top5_lines = "\n".join([
        f"  - IMP:{p['imp']} / ENG率:{p['eng_rate']}% / リプライ:{p['replies']} / プロフクリック:{p['profile_clicks']}\n"
        f"    本文冒頭: 「{p['text'][:60].replace(chr(10), ' ')}...」"
        for p in analysis['top5']
    ])

    schedule_lines = "\n".join([f"  - {date} {time}" for date, time in schedule])
    count = len(schedule)

    return f"""あなたはIMA検定（インターネットマーケティング検定）のX（旧Twitter）投稿コンテンツを作成する専門家です。
以下の実績データとXアルゴリズムに基づいて、最適化された投稿文を{count}本生成してください。

---
## 過去投稿の実績データ分析（広告除外・有機投稿のみ）

- 分析対象投稿数: {analysis['total']}件
- 平均IMP: {analysis['avg_imp']}
- 平均エンゲージメント率: {analysis['avg_eng']}%
- 累計リプライ数: {analysis['total_replies']}件
- 累計プロフクリック数: {analysis['total_profile']}件

### コンテンツタイプ別の効果
| タイプ | 件数 | 平均IMP |
|---|---|---|
| 問いかけあり | {analysis['q_count']}件 | {analysis['q_avg_imp']} |
| 問いかけなし | {analysis['total'] - analysis['q_count']}件 | {analysis['no_q_avg_imp']} |
| URLあり | {analysis['url_count']}件 | {analysis['url_avg_imp']} |
| URLなし | {analysis['total'] - analysis['url_count']}件 | {analysis['no_url_avg_imp']} |
| スレッド形式 | {analysis['thread_count']}件 | （スレッドは最高リプライ獲得率） |

### トップ5投稿（エンゲージメント率順）
{top5_lines}

---
{ALGORITHM_SUMMARY}

---
{IMA_BRAND_CONTEXT}

---
## 生成要件

以下のスケジュールで{count}本の投稿を生成してください:
{schedule_lines}

申込み締切: {deadline}（この締切に向けて、後半の投稿ほど申込み誘導を強化すること）

**必須ルール（全投稿共通）**:
1. 末尾に具体的な問いかけを必ず入れる（例: 「あなたはどちらですか？↓コメントで教えてください」）
2. 「プロフィールのリンクから👇」などプロフィール誘導の一行を含める
3. 本文にURLを絶対に入れない（申込みURLが必要な場合はcontentの最後の要素として自己リプライ形式で追加）
4. 1本目は必ずスレッド形式（3〜4ツイート）にする
5. ハッシュタグは1投稿あたり2〜3個のみ
6. 各投稿のテーマは重複させない

**推奨ハッシュタグ**: #AIマーケティング #IMA検定 #デジタルマーケティング #Webマーケ #AIスキル #マーケティング資格 #Google広告 #GA4

---
## 出力形式

以下のJSON形式のみで出力してください。JSONの前後に説明文を入れないでください。

```json
[
  {{
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "content": ["ツイート1本文", "ツイート2本文（スレッドの場合）"],
    "image": null,
    "is_thread": true,
    "is_posted": false,
    "generation_note": "この投稿の狙い（アルゴリズム観点での一言説明）"
  }}
]
```

スレッド投稿の場合、contentの最初の要素がタイムラインに表示されるメインツイートです。
URLが必要な場合は、contentの最後の要素に自己リプライとして追加してください。
"""


def call_gemini_api(prompt, api_key):
    """Gemini APIを呼び出して投稿文を生成"""
    print("⏳ Gemini APIで投稿文を生成中...")

    model = "gemini-3.1-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    system_instruction = "あなたはX（旧Twitter）のコンテンツ戦略の専門家です。指示通りのJSON形式のみを返してください。JSONの前後に説明文を入れないでください。"
    body = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=body, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API エラー ({resp.status_code}): {resp.text}")

    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def parse_json_response(raw_text):
    """レスポンスからJSONを抽出してパース"""
    match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw_text, re.DOTALL)
    json_str = match.group(1).strip() if match else raw_text.strip()
    return json.loads(json_str)


def save_drafts(posts):
    """ドラフトをMarkdownとJSONで保存"""
    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# 自動生成投稿ドラフト",
        f"**生成日**: {today}  ",
        f"**投稿数**: {len(posts)}件  ",
        "",
        "---",
        "",
    ]

    for i, post in enumerate(posts, 1):
        fmt = f"スレッド（{len(post['content'])}ツイート）" if post.get('is_thread') else "シングル"
        lines += [
            f"## 投稿{i} ／ {post['date']}（{post['time']}）",
            f"**形式**: {fmt}  ",
            f"**狙い**: {post.get('generation_note', '')}  ",
            "",
        ]
        for j, tweet in enumerate(post['content']):
            if post.get('is_thread'):
                lines.append(f"### ツイート {j+1}/{len(post['content'])}")
            lines += ["```", tweet, "```", ""]
        lines += ["---", ""]

    lines += [
        "> ✅ 内容を確認後、以下を実行して投稿キューに追加してください:",
        "> ```bash",
        "> python3 approve_posts.py",
        "> ```",
    ]

    with open(DRAFT_MD_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # generation_noteを含めたままJSONに保存（approve_posts.pyで除去）
    with open(DRAFT_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    print(f"✅ ドラフト保存完了:")
    print(f"   レビュー用MD : {DRAFT_MD_FILE}")
    print(f"   承認用JSON  : {DRAFT_JSON_FILE}")


def main():
    parser = argparse.ArgumentParser(description='X投稿文をGemini APIで自動生成')
    parser.add_argument('--csv', required=True, help='X Analytics CSVファイルのパス')
    parser.add_argument('--count', type=int, default=4, help='生成する投稿数（デフォルト: 4）')
    parser.add_argument('--start', help='投稿開始日 YYYY-MM-DD（デフォルト: 次の月曜日）')
    parser.add_argument('--deadline', default='2026-06-09', help='申込み締切日（デフォルト: 2026-06-09）')
    args = parser.parse_args()

    api_key = load_env()

    if not os.path.exists(args.csv):
        print(f"❌ エラー: CSVファイルが見つかりません: {args.csv}")
        exit(1)

    print(f"📊 CSVを分析中: {args.csv}")
    analysis = analyze_csv(args.csv)
    if not analysis:
        print("❌ エラー: CSVに有効なデータがありません（広告除外後の投稿が0件）")
        exit(1)

    print(f"   有機投稿数: {analysis['total']}件 / 平均IMP: {analysis['avg_imp']} / 問いかけあり: {analysis['q_count']}件")

    schedule = build_schedule(args.start, args.count)
    print(f"📅 投稿スケジュール:")
    for date, time in schedule:
        print(f"   - {date} {time}")

    prompt = build_prompt(analysis, schedule, args.deadline)
    raw = call_gemini_api(prompt, api_key)

    try:
        posts = parse_json_response(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        print("--- 生レスポンス ---")
        print(raw)
        exit(1)

    print(f"✅ {len(posts)}件の投稿文を生成しました")
    save_drafts(posts)


if __name__ == "__main__":
    main()
