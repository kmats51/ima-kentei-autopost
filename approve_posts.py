"""
投稿承認・キュー追加スクリプト

使い方:
  python3 approve_posts.py           # 対話形式（1件ずつ確認）
  python3 approve_posts.py --auto    # 全件自動承認・自動プッシュ

generate_posts.py で生成した draft_posts.json を読み込み、
承認した投稿を post_data.json に追加、GitHubへプッシュする。
"""

import os
import json
import argparse
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFT_JSON = os.path.join(BASE_DIR, 'draft_posts.json')
DRAFT_MD = os.path.join(BASE_DIR, 'draft_posts.md')
POST_DATA = os.path.join(BASE_DIR, 'post_data.json')


def print_post(post, index, total):
    """投稿の内容を見やすく表示"""
    fmt = f"スレッド（{len(post['content'])}ツイート）" if post.get('is_thread') else "シングル"
    note = post.get('generation_note', '')

    print(f"\n{'='*60}")
    print(f"【投稿 {index}/{total}】{post['date']} {post['time']} ／ {fmt}")
    if note:
        print(f"狙い: {note}")
    print('-'*60)

    for j, tweet in enumerate(post['content']):
        if post.get('is_thread'):
            print(f"\n--- ツイート {j+1}/{len(post['content'])} ---")
        print(tweet)

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true', help='全件自動承認・自動プッシュ（確認なし）')
    args = parser.parse_args()

    if not os.path.exists(DRAFT_JSON):
        print(f"❌ {DRAFT_JSON} が見つかりません。")
        print("   先に generate_posts.py を実行してください:")
        print("   python3 generate_posts.py --csv path/to/analytics.csv")
        exit(1)

    with open(DRAFT_JSON, 'r', encoding='utf-8') as f:
        drafts = json.load(f)

    if not drafts:
        print("ドラフトが空です。")
        exit(0)

    approved = []

    if args.auto:
        print(f"\n🤖 自動承認モード: {len(drafts)}件をすべて承認します\n")
        for post in drafts:
            print_post(post, drafts.index(post) + 1, len(drafts))
            clean = {k: v for k, v in post.items() if k != 'generation_note'}
            approved.append(clean)
    else:
        print(f"\n📋 投稿ドラフトの確認（{len(drafts)}件）")
        print("   各投稿を確認してY（承認）/ n（スキップ）/ q（中断）で応答してください\n")

        for i, post in enumerate(drafts, 1):
            print_post(post, i, len(drafts))

            while True:
                answer = input("\n  承認しますか？ [Y/n/q]: ").strip().lower()
                if answer in ('', 'y', 'yes'):
                    clean = {k: v for k, v in post.items() if k != 'generation_note'}
                    approved.append(clean)
                    print("  ✅ 承認しました")
                    break
                elif answer in ('n', 'no'):
                    print("  ❌ スキップしました")
                    break
                elif answer in ('q', 'quit'):
                    print("\n中断しました。承認済みの投稿のみ処理します。")
                    break
                else:
                    print("  Y（承認）/ n（スキップ）/ q（中断）のいずれかを入力してください")
            else:
                continue
            if answer in ('q', 'quit'):
                break

    if not approved:
        print("\n承認された投稿がありません。終了します。")
        exit(0)

    print(f"\n✅ {len(approved)}件を承認しました")

    # 既存の post_data.json を読み込んで重複チェック
    with open(POST_DATA, 'r', encoding='utf-8') as f:
        existing = json.load(f)

    existing_keys = {f"{p['date']} {p['time']}" for p in existing}
    new_posts = []
    skipped = []

    for post in approved:
        key = f"{post['date']} {post['time']}"
        if key in existing_keys:
            skipped.append(key)
        else:
            new_posts.append(post)

    if skipped:
        print(f"⚠️  重複のためスキップ: {', '.join(skipped)}")

    if not new_posts:
        print("追加できる新規投稿がありませんでした（すべて重複）。")
        exit(0)

    # 日付順にソートして追記
    existing.extend(new_posts)
    existing.sort(key=lambda p: f"{p['date']} {p['time']}")

    with open(POST_DATA, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=4, ensure_ascii=False)

    print(f"✅ {len(new_posts)}件を post_data.json に追加しました")
    for p in new_posts:
        fmt = "スレッド" if p.get('is_thread') else "シングル"
        print(f"   - {p['date']} {p['time']} （{fmt}）")

    # GitHubへのプッシュ確認（--autoなら確認なしでプッシュ）
    if not args.auto:
        print()
        answer = input("GitHubにプッシュして自動投稿を有効化しますか？ [Y/n]: ").strip().lower()
        if answer not in ('', 'y', 'yes'):
            print("プッシュをスキップしました（手動で git push してください）")
            exit(0)

    date_range = f"{new_posts[0]['date']}〜{new_posts[-1]['date']}"
    commit_msg = f"Auto: {len(new_posts)}件の生成投稿を追加 ({date_range})"

    result = subprocess.run(
        ['git', 'add', 'post_data.json'],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ git add 失敗: {result.stderr}")
        exit(1)

    result = subprocess.run(
        ['git', 'commit', '-m', commit_msg],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ git commit 失敗: {result.stderr}")
        exit(1)

    result = subprocess.run(
        ['git', 'push', 'origin', 'main'],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ git push 失敗: {result.stderr}")
        exit(1)

    print(f"✅ GitHubにプッシュしました（{commit_msg}）")
    print("   GitHub Actionsが次の定刻（07:01 or 12:01 JST）に自動投稿します")

    # ドラフトファイルをクリア（処理済み）
    with open(DRAFT_JSON, 'w', encoding='utf-8') as f:
        json.dump([], f)
    print("   draft_posts.json をクリアしました")


if __name__ == "__main__":
    main()
