import os
import logging
from typing import List, Dict, Set

from dotenv import load_dotenv
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk.errors import SlackApiError

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bolt App
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True,  # Cloud Runなどでレスポンスを返す前に処理を完了させるための設定
)

# Initialize Flask App
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

import time

class SimpleCache:
    """簡易的なインメモリキャッシュ"""
    def __init__(self, ttl_seconds=3600):
        self.ttl_seconds = ttl_seconds
        self._cache = {}
        self._timestamps = {}

    def get(self, key):
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl_seconds:
                return self._cache[key]
        return None

    def set(self, key, value):
        self._cache[key] = value
        self._timestamps[key] = time.time()

# ユーザー情報のキャッシュ (1時間)
user_cache = SimpleCache(ttl_seconds=3600)

def get_all_channel_members(client, channel_id: str) -> Set[str]:
    """チャンネルの全メンバーIDを取得する（ページネーション対応）"""
    members = set()
    cursor = None
    while True:
        try:
            response = client.conversations_members(
                channel=channel_id,
                cursor=cursor,
                limit=1000
            )
            members.update(response["members"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.error(f"Error fetching members: {e}")
            break
    return members


def get_all_users_info(client) -> Dict[str, Dict]:
    """ワークスペースの全ユーザー情報を取得して辞書化する（キャッシュ対応）"""
    # キャッシュを確認
    cache_key = "all_users"
    cached_data = user_cache.get(cache_key)
    if cached_data:
        logger.info("Using cached user data.")
        return cached_data

    logger.info("Fetching user data from Slack API...")
    users_info = {}
    cursor = None
    while True:
        try:
            response = client.users_list(cursor=cursor, limit=1000)
            for user in response["members"]:
                users_info[user["id"]] = user
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.error(f"Error fetching users list: {e}")
            break
    
    # キャッシュに保存
    if users_info:
        user_cache.set(cache_key, users_info)
    
    return users_info


@app.shortcut("get_reaction_users")
def handle_shortcut(ack, body, client):
    """メッセージショートカットが実行されたときにモーダルを開く"""
    ack()

    message_ts = body['message']['ts']
    channel_id = body['channel']['id']
    
    # モーダルの表示
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "reaction_stats_modal",
            "private_metadata": f"{channel_id}|{message_ts}",  # チャンネルIDとメッセージTSを引き継ぐ
            "title": {"type": "plain_text", "text": "リアクション集計設定"},
            "submit": {"type": "plain_text", "text": "集計する"},
            "close": {"type": "plain_text", "text": "キャンセル"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "このメッセージのリアクション状況を集計し、DMでレポートを送信します。"
                    }
                },
                {
                    "type": "input",
                    "block_id": "options",
                    "label": {"type": "plain_text", "text": "オプション"},
                    "element": {
                        "type": "checkboxes",
                        "action_id": "checkboxes",
                        "options": [
                            {
                                "text": {"type": "plain_text", "text": "未リアクションのユーザーも表示する"},
                                "value": "include_no_reaction"
                            }
                        ]
                    },
                    "optional": True
                }
            ]
        }
    )


@app.view("reaction_stats_modal")
def handle_view_submission(ack, body, client, view, logger):
    """モーダル送信時の処理"""
    ack()

    user_id = body["user"]["id"]
    metadata = view["private_metadata"]
    channel_id, message_ts = metadata.split("|")

    # オプションの値を取得
    selected_options = view["state"]["values"]["options"]["checkboxes"]["selected_options"]
    include_no_reaction = any(opt["value"] == "include_no_reaction" for opt in selected_options)

    # ユーザーに「集計中」のメッセージを一時的に送る（処理が長い場合用）
    # Cloud Runの制約を考慮し、ack後に非同期的に実行されるわけではないフレームワークの都合上、
    # ここで重い処理をすると再送が起きるリスクがあるが、
    # Python Boltのデフォルト＋Flaskアダプタであればリクエスト内で処理される。
    # 3秒ルールを守るには lazy listenerを使うべきだが、構成をシンプルにするため
    # まずはインラインで実行し、もしタイムアウトするなら非同期化を検討する。
    # 今回はチャットへの投稿で終わるので、多少時間がかかってもSlack側はViewのcloseをしてくれる。

    try:
        # 必要なデータを取得
        # 1. リアクション取得
        reactions_resp = client.reactions_get(channel=channel_id, timestamp=message_ts)
        message = reactions_resp.get("message", {})
        reactions = message.get("reactions", [])
        
        # 2. 全ユーザー情報取得（Bot判定のためキャッシュ作成）
        all_users = get_all_users_info(client)
        
        # 3. チャンネルメンバー取得
        channel_members_ids = get_all_channel_members(client, channel_id)

        # データの整理
        # Botを除外した有効なメンバーIDのセット
        valid_member_ids = {
            uid for uid in channel_members_ids 
            if uid in all_users 
            and not all_users[uid].get("is_bot") 
            and not all_users[uid].get("deleted")
            and uid != "USLACKBOT"
        }

        # リアクションごとの集計
        reaction_counts = []
        reacted_user_ids = set()

        for reaction in reactions:
            users = reaction.get("users", [])
            # Bot以外のリアクションユーザーをフィルタリング
            valid_users = [u for u in users if u in valid_member_ids]
            
            if valid_users:
                reaction_counts.append({
                    "name": reaction["name"],
                    "count": len(valid_users),
                    "users": valid_users
                })
                reacted_user_ids.update(valid_users)
        
        # リアクション数順にソート（多い順）
        reaction_counts.sort(key=lambda x: x["count"], reverse=True)

        not_reacted_user_ids = list(valid_member_ids - reacted_user_ids)
        
        # レポートのBlock作成
        
        # 元のメッセージURL
        message_url = f"https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "リアクション状況の一覧",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"元のメッセージ: <{message_url}|リンク>"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*統計情報* (Bot除く)\n"
                        f"• リアクション済: {len(reacted_user_ids)}人\n"
                        f"• 全メンバー数: {len(valid_member_ids)}人\n"
                        f"• 未リアクション: {len(not_reacted_user_ids)}人"
                    )
                }
            },
            {"type": "divider"}
        ]

        # リアクション詳細
        for idx, r in enumerate(reaction_counts):
            # 画像のように数字アイコンを使いたいが、標準emojiで近いものを代用
            # 1️⃣, 2️⃣ など
            rank_icon = f"{idx + 1}️⃣" if idx < 10 else "•"
            
            user_mentions = [f"<@{u}>" for u in r["users"]]
            user_mentions_str = ", ".join(user_mentions)
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{rank_icon} (人数: {r['count']}) : {user_mentions_str}"
                }
            })

        # 未リアクションユーザー表示（オプション有効時）
        if include_no_reaction and not_reacted_user_ids:
            blocks.append({"type": "divider"})
            
            # ユーザー数が多い場合、ブロックを分割する（Slackの1ブロックの文字数制限対策）
            chunk_size = 50  # 1ブロックあたりの最大表示人数（適当な調整）
            for i in range(0, len(not_reacted_user_ids), chunk_size):
                chunk = not_reacted_user_ids[i:i + chunk_size]
                chunk_mentions = [f"<@{u}>" for u in chunk]
                
                start_num = i + 1
                end_num = min(i + chunk_size, len(not_reacted_user_ids))
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*未リアクションのユーザー* ({len(not_reacted_user_ids)}人中 {start_num}〜{end_num}人目):\n" + ", ".join(chunk_mentions)
                    }
                })

        # DM送信
        client.chat_postMessage(
            channel=user_id,
            text="リアクション状況の集計結果",
            blocks=blocks
        )

    except Exception as e:
        logger.error(f"Error in view submission: {e}")
        client.chat_postMessage(
            channel=user_id,
            text=f"エラーが発生しました: {e}"
        )


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)
