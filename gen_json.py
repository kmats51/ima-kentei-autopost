import json
import re
import os
from datetime import datetime, timedelta, timezone

# パス設定（IMA検定ディレクトリを使用）
root_dir = os.path.dirname(os.path.abspath(__file__))
md_path = os.path.join(root_dir, '2026-03-20_imakentei_2週間投稿コンテンツ案.md')
img_dir = os.path.join(root_dir, '投稿用画像')
output_path = os.path.join(root_dir, 'post_data.json')

# 日本時間(JST)を設定
jst = timezone(timedelta(hours=9))
now = datetime.now(jst)

# 既存の投稿済みフラグを保持するため、現在のJSONを読み込む
existing_posts = {}
if os.path.exists(output_path):
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = f.read()
            # 競合マーカーがある場合は無視して新規生成
            if '<<<<<<<' not in data:
                old_data = json.loads(data)
                for p in old_data:
                    key = f"{p['date']} {p['time']}"
                    existing_posts[key] = p.get('is_posted', False)
    except Exception as e:
        print(f"Warning: Could not read existing post_data.json: {e}")

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 各Dayのセクションに分割
days = list(re.split(r'### Day\d+', content))[1:]
post_data = []

# 日付のリスト
dates = [
    '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', '2026-03-28', '2026-03-29',
    '2026-03-30', '2026-03-31', '2026-04-01', '2026-04-02', '2026-04-03', '2026-04-04', '2026-04-05'
]

for i, day_content in enumerate(days):
    if i >= len(dates): break
    date = dates[i]
    
    # 時間を 07:00 か 12:00 に固定
    time_match = re.search(r'⏰ (?:昼|朝) (\d{2}:\d{2})', day_content)
    if time_match:
        hour = int(time_match.group(1).split(':')[0])
        post_time = '07:00' if hour <= 9 else '12:00'
    else:
        post_time = '07:00'

    # 全てのコードブロックを抽出（スレッド対応）
    body_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', day_content, re.DOTALL)
    if not body_blocks: continue
    
    main_text = body_blocks[0].strip()
    is_thread = '【スレッド🧵】' in main_text or '【スレッド🧵】' in day_content or 'スレッド型' in day_content
    
    if is_thread:
        thread_items = [b.strip() for b in body_blocks if b.strip()]
    else:
        thread_items = [main_text]
    
    # 图片（相対パス）
    img_filename = f'{date}.png'
    img_rel_path = f'投稿用画像/{img_filename}'
    img_abs_path = os.path.join(img_dir, img_filename)
    has_image = os.path.exists(img_abs_path)
    
    key = f"{date} {post_time}"
    # 過去の日付・時刻であれば自動的に True、そうでなければ既存の値を採用、既存もなければ False
    post_datetime = datetime.strptime(key, '%Y-%m-%d %H:%M').replace(tzinfo=jst)
    is_posted = existing_posts.get(key, now >= post_datetime)

    post_data.append({
        'date': date,
        'time': post_time,
        'content': thread_items,
        'image': img_rel_path if has_image else None,
        'is_thread': is_thread,
        'is_posted': is_posted
    })

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(post_data, f, indent=4, ensure_ascii=False)

print(f"Update: Created/Updated post_data.json with {len(post_data)} days of content.")
