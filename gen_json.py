import json
import re
import os
from pathlib import Path

from datetime import datetime, timedelta

# --- 設定 ---
# 読み込むMarkdownファイルの名前
TARGET_MD = '2026-03-20_imakentei_2週間投稿コンテンツ案.md'
# Day1 の投稿開始日 (YYYY-MM-DD形式)
START_DATE = '2026-03-23'
# -----------

# クライアントの環境・GitHub両方で動くように相対パスで定義
base_dir = Path(__file__).parent
md_path = base_dir / TARGET_MD
img_dir = base_dir / '投稿用画像'
output_path = base_dir / 'post_data.json'

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 各Dayのセクションに分割
days = list(re.split(r'### Day\d+', content))[1:]
post_data = []

# 日付リストを START_DATE から自動で生成する
start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
dates = [(start_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(len(days))]

# 既存のデータを読み込み（is_postedフラグを維持するため）
existing_data = {}
if output_path.exists():
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                key = f"{item['date']}_{item['time']}"
                existing_data[key] = item.get('is_posted', False)
    except:
        pass

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

    # 本文抽出
    body_match = re.search(r'```(?:\w+)?\n(.*?)```', day_content, re.DOTALL)
    if not body_match: continue
    body_text = body_match.group(1).strip()
    
    # 画像（相対パスで保存する）
    img_name = f'{date}.png'
    img_path = img_dir / img_name
    has_image = img_path.exists()
    rel_img_path = f"投稿用画像/{img_name}" if has_image else None
    
    # スレッド
    is_thread = '【スレッド🧵】' in body_text or '【保存推奨🔖】' in body_text
    if is_thread:
        thread_items = [p.strip() for p in re.split(r'\n---\n', body_text) if p.strip()]
    else:
        thread_items = [body_text]

    # フラグの復元
    key = f"{date}_{post_time}"
    is_posted = existing_data.get(key, False)

    post_data.append({
        'date': date,
        'time': post_time,
        'content': thread_items,
        'image': rel_img_path,
        'is_thread': is_thread,
        "is_posted": is_posted
    })

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(post_data, f, indent=4, ensure_ascii=False)
print(f"Created/Updated post_data.json (相対パス & is_postedフラグ対応)")
