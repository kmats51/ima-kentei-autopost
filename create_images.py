import os
from PIL import Image, ImageDraw, ImageFont

# 画像保存ディレクトリ
output_dir = '/Users/kouichimatsumoto/Vault/IMA検定/X_Algorithm/投稿用画像'
os.makedirs(output_dir, exist_ok=True)

def create_impact_image(filename, title, subtitle, items, main_color="#1DA1F2"):
    """
    インパクトのある高品質なインフォグラフィックを生成する
    """
    width, height = 1200, 675  # 16:9
    image = Image.new('RGB', (width, height), color='#F8F9FA')  # 薄いグレー背景
    draw = ImageDraw.Draw(image)
    
    # フォント設定
    try:
        font_h1 = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 65)
        font_h2 = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 35)
        font_body = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 45)
        font_emoji = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 50)
    except:
        font_h1 = ImageFont.load_default()
        font_h2 = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_emoji = ImageFont.load_default()

    # 背景にアクセントの矩形（左側）
    draw.rectangle([0, 0, 40, height], fill=main_color)
    
    # ヘッダー領域の装飾
    draw.rectangle([60, 40, width-40, 160], fill="white", outline=main_color, width=2)
    draw.text((80, 75), title, font=font_h1, fill="#222222")
    
    # サブタイトル
    draw.text((80, 185), subtitle, font=font_h2, fill="#666666")
    
    # カードデザイン（箇条書き）
    for i, (emoji, text) in enumerate(items):
        y = 260 + (i * 130)
        # 影
        draw.rectangle([80+5, y+5, width-80+5, y+100+5], fill="#E9ECEF")
        # メインカード
        draw.rectangle([80, y, width-80, y+100], fill="white", outline="#DEE2E6", width=1)
        # 絵文字とテキスト
        draw.text((115, y+25), emoji, font=font_emoji, fill="black")
        draw.text((200, y+25), text, font=font_body, fill="#333333")

    # フッター
    draw.text((width-250, height-60), "@imakentei", font=font_h2, fill="#AAAAAA")
    
    save_path = os.path.join(output_dir, filename)
    image.save(save_path)
    print(f"Impact Image Created: {save_path}")

# --- 4月1日 (Day 10): 検索クエリ仕分け ---
create_impact_image(
    "2026-04-01.png", 
    "AIで検索クエリを仕分ける技術", 
    "広告費の20~30%を占める『無駄』をAIで即時カットします",
    [
        ("💎", "お宝クエリ：CV期待値が極めて高い（予算集中）"),
        ("🗑️", "ノイズクエリ：ターゲット外。完全一致で即除外へ"),
        ("🤔", "検討クエリ：検索意図をAIに判断させ、施策を練る")
    ],
    "#17BF63" # Vibrant Green
)

# --- 4月4日 (Day 13): LPチェックリスト ---
create_impact_image(
    "2026-04-04.png", 
    "LP改善 究極のチェックリスト", 
    "CVRを2%→4%に引き上げ、CV数を2倍にするための鉄則",
    [
        ("🔗", "広告文とLPのメッセージに『ズレ』はないか？"),
        ("🎨", "ターゲットとデザインのトーンは合っているか？"),
        ("📄", "フォームの項目数は、最小限に絞られているか？")
    ],
    "#F58220" # Vibrant Orange
)
