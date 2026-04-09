import json
import re
import os
from datetime import datetime, timedelta, timezone

def process_slot(date, post_time, content, post_list, img_dir, existing_posts, now, jst):
    # コードブロックを抽出
    body_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
    if not body_blocks:
        return
    
    main_text = body_blocks[0].strip()
    
    # スレッド判定
    is_thread = '【スレッド🧵】' in main_text or '【スレッド🧵】' in content or 'スレッド型' in content
    
    if is_thread:
        thread_items = [b.strip() for b in body_blocks if b.strip()]
    else:
        thread_items = [main_text]
    
    # 画像判定：テキスト内に「※画像添付」または具体的な日付画像への言及がある場合
    has_img_in_text = '※画像添付' in content or 'png' in content or '図解' in content
    img_filename = f'{date}.png'
    img_rel_path = f'投稿用画像/{img_filename}'
    img_abs_path = os.path.join(img_dir, img_filename)
    
    # ファイルが存在し、かつテキスト内で画像に言及している場合のみ紐付け
    has_image = os.path.exists(img_abs_path) and has_img_in_text
    
    key = f"{date} {post_time}"
    try:
        post_datetime = datetime.strptime(key, '%Y-%m-%d %H:%M').replace(tzinfo=jst)
        # 過去ならTrue、未投稿なら既存データから取得（それもなければ現在時刻と比較）
        is_posted = existing_posts.get(key, now >= post_datetime)
    except:
        is_posted = existing_posts.get(key, False)

    post_list.append({
        'date': date,
        'time': post_time,
        'content': thread_items,
        'image': img_rel_path if has_image else None,
        'is_thread': is_thread,
        'is_posted': is_posted
    })

def main():
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
                if '<<<<<<' not in data:
                    old_data = json.loads(data)
                    for p in old_data:
                        key = f"{p['date']} {p['time']}"
                        existing_posts[key] = p.get('is_posted', False)
        except:
            pass

    with open(md_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # 日付リスト（Day1〜Day14）
    dates = [
        '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', 
        '2026-03-28', '2026-03-29', '2026-03-30', '2026-04-10', '2026-04-11', 
        '2026-04-12', '2026-04-13', '2026-04-14', '2026-04-15'
    ]

    # Dayごとに分割
    day_sections = list(re.split(r'### Day\d+', full_content))[1:]
    post_data_list = []

    for i, day_section in enumerate(day_sections):
        if i >= len(dates):
            break
        date = dates[i]
        
        # セクション内で「#### ⏰」を探す（1日複数投稿対応）
        slots = list(re.split(r'#### ⏰', day_section))
        if len(slots) > 1:
            # 1スロット目はヘッダーなのでスキップ
            for slot_content in slots[1:]:
                time_match = re.search(r'(\d{2}:\d{2})', slot_content)
                if time_match:
                    process_slot(date, time_match.group(1), slot_content, post_data_list, img_dir, existing_posts, now, jst)
        else:
            # 従来形式（1日1投稿）
            time_match = re.search(r'⏰ (?:昼|朝) (\d{2}:\d{2})', day_section)
            post_time = time_match.group(1) if time_match else '07:00'
            process_slot(date, post_time, day_section, post_data_list, img_dir, existing_posts, now, jst)

    # 書き出し
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(post_data_list, f, indent=4, ensure_ascii=False)
    
    print(f"Success: Updated post_data.json with {len(post_data_list)} slots.")

if __name__ == "__main__":
    main()
