import os
import logging  # 追加
from datetime import datetime, timedelta
from os.path import dirname, join
from typing import Set, List
from collections import defaultdict
import sys
from time import sleep

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_bolt.oauth.oauth_settings import OAuthSettings

# ロギングの設定を追加
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(verbose=True)
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

__version__ = "1.0.0"
APP_NAME = "Reaction Indexer"

# グローバル変数として定義（ファイルの先頭付近）
app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    logger=logger
)

# WebClientをグローバルで直接初期化
client = WebClient(
    token=os.getenv("SLACK_BOT_TOKEN"),
    logger=logger
)

def initialize_app():
    """アプリケーションの初期化"""
    try:
        logger.info("Initializing app...")
        
        # 接続テスト
        logger.info("Testing Slack connection...")
        auth_test = client.auth_test()
        logger.info(f"Connected as {auth_test['user']} to {auth_test['team']}")
        
        # スコープの確認
        logger.info("Checking app scopes...")
        auth_result = client.auth_test()
        logger.info(f"App scopes: {auth_result.get('scope', 'No scope information')}")
        
        return True
    except Exception as e:
        logger.exception("Error initializing app")
        raise e

# authorize関数をここに移動
@app.middleware
def handle_authorization(logger, body, next):
    try:
        return next()
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        raise

# レート制限の実装
class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)

    def is_allowed(self, user_id):
        now = datetime.now()
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if now - req_time < timedelta(seconds=self.time_window)
        ]
        
        if len(self.requests[user_id]) >= self.max_requests:
            return False
            
        self.requests[user_id].append(now)
        return True

rate_limiter = RateLimiter()

def validate_user_access(client, user_id, channel_id):
    """ユーザーがチャンネルにアクセス可能か確認"""
    try:
        result = client.conversations_members(channel=channel_id, limit=1)
        return True
    except Exception:
        return False

@app.shortcut("get_reaction_users")
def handle_get_reactions(ack, body, client, logger):
    try:
        logger.info("=== Shortcut Triggered ===")
        # ショートカットを実行したユーザーのIDを取得して記録
        shortcut_user_id = body['user']['id']
        logger.info(f"Shortcut triggered by user: {shortcut_user_id}")
        
        # 即座にackを返す
        ack()
        logger.info("Acknowledged shortcut")
        
        # 少し待機してからモーダルを開く
        sleep(0.5)  # 0.5秒待機
        
        user_id = body['user']['id']
        logger.info(f"Processing request for user: {user_id}")
        
        if not rate_limiter.is_allowed(user_id):
            # レート制限の場合はエラーメッセージを送信
            client.chat_postMessage(
                channel=user_id,
                text="リクエストが多すぎます。しばらく待ってから再試行してください。"
            )
            return

        message_id = body['message']['ts']
        channel_id = body['channel']['id']
        logger.info(f"Message ID: {message_id}, Channel ID: {channel_id}")

        # アクセス権限の確認
        if not validate_user_access(client, user_id, channel_id):
            client.chat_postMessage(
                channel=user_id,
                text="このチャンネルへのアクセス権限がありません。"
            )
            return

        logger.info("Processing reaction request")
        # メッセージに対するリアクションを取得
        response = client.reactions_get(channel=channel_id, timestamp=message_id)
        message = response['message']

        # モーダルを表示する際に、ショートカットを実行したユーザーのIDも含める
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "reaction_options",
                # private_metadataにショートカット実行者のIDを含める
                "private_metadata": f"{channel_id}|{message_id}|{shortcut_user_id}",
                "title": {
                    "type": "plain_text",
                    "text": "リアクション一覧オプション"
                },
                "submit": {
                    "type": "plain_text",
                    "text": "表示"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "表示オプションを選択してください："
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "show_non_reacted",
                        "element": {
                            "type": "checkboxes",
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "未リアクションのユーザーも表示する"
                                    },
                                    "value": "show_non_reacted"
                                }
                            ],
                            "action_id": "checkbox"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "表示オプション"
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.exception("Error in handle_get_reactions")
        client.chat_postMessage(
            channel=shortcut_user_id,  # エラー時もショートカット実行者にDMを送信
            text=f"エラーが発生しました: {str(e)}"
        )

def get_users_info(client, user_ids: List[str]) -> dict:
    """複数ユーザーの情報を一括で取得する"""
    users_info = {}
    try:
        # users.list APIを使用して全ユーザー情報を一度に取得
        response = client.users_list()
        all_users = response['members']
        
        # ページネーションがある場合は続けて取得
        while response.get('response_metadata', {}).get('next_cursor'):
            cursor = response['response_metadata']['next_cursor']
            response = client.users_list(cursor=cursor)
            all_users.extend(response['members'])

        # 必要なユーザーの情報だけを抽出
        for user in all_users:
            if user['id'] in user_ids:
                users_info[user['id']] = {
                    'is_bot': user.get('is_bot', False),
                    'is_app_user': user.get('is_app_user', False),
                    'deleted': user.get('deleted', False)
                }
        
        logger.info(f"Retrieved {len(users_info)} user info out of {len(user_ids)} requested")
        
    except Exception as e:
        logger.error(f"Error fetching users info: {e}")
    
    return users_info

@app.view("reaction_options")
def handle_reaction_options_submission(ack, body, client, logger):
    # 即座にackを返して処理時間を確保
    ack()
    logger.info("Modal submission acknowledged")
    
    try:
        # モーダルから情報を取得（ショートカット実行者のIDを含む）
        metadata = body["view"]["private_metadata"].split("|")
        channel_id, message_id, shortcut_user_id = metadata  # user_idをshortcut_user_idに変更
        logger.info(f"Processing request for shortcut user: {shortcut_user_id}")

        # チェックボックスの状態を取得
        show_non_reacted = False
        try:
            state_values = body["view"]["state"]["values"]
            selected_options = state_values["show_non_reacted"]["checkbox"]["selected_options"]
            show_non_reacted = len(selected_options) > 0
            logger.info(f"Show non-reacted users: {show_non_reacted}")
        except Exception as e:
            logger.warning(f"Error getting checkbox value: {e}")

        # メッセージに対するリアクションを取得
        logger.info("Fetching reactions...")
        response = client.reactions_get(channel=channel_id, timestamp=message_id)
        message = response['message']
        logger.info("Reactions fetched successfully")

        # ワークスペース情報を取得
        logger.info("Fetching workspace info...")
        workspace_info = client.team_info()
        workspace_domain = workspace_info["team"]["domain"]
        logger.info(f"Workspace domain: {workspace_domain}")

        # チャンネルのメンバー一覧を取得（未リアクション表示が必要な場合のみ）
        all_members = set()
        if show_non_reacted:
            try:
                logger.info(f"Fetching members for channel: {channel_id}")
                members_response = client.conversations_members(channel=channel_id)
                logger.info(f"Initial members response: {members_response}")
                
                all_members = set(members_response['members'])
                logger.info(f"Initial member count: {len(all_members)}")
                
                while members_response.get('response_metadata', {}).get('next_cursor'):
                    cursor = members_response['response_metadata']['next_cursor']
                    logger.info(f"Fetching more members with cursor: {cursor}")
                    
                    members_response = client.conversations_members(
                        channel=channel_id,
                        cursor=cursor
                    )
                    new_members = set(members_response['members'])
                    all_members.update(new_members)
                    logger.info(f"Added {len(new_members)} more members. Total: {len(all_members)}")
            except Exception as e:
                logger.exception("Error fetching channel members")
                # エラーが発生しても処理を継続
                all_members = set()

        reacted_users: Set[str] = set()
        blocks = []

        if 'reactions' in message:
            reactions = message['reactions']
            logger.info(f"Processing {len(reactions)} reactions")
        else:
            logger.info("No reactions found in message")
            reactions = []

        # リアクションをしたユーザーの一覧を作成
        for reaction in reactions:
            users = reaction['users']
            reacted_users.update(users)
            user_mentions = [f"<@{user}>" for user in users]
            user_mentions_str = ', '.join(user_mentions)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":{reaction['name']}: (人数: {len(users)}) : {user_mentions_str}"
                }
            })

        if show_non_reacted:
            blocks.append({"type": "divider"})

        # 未リアクションユーザーの表示（オプションが選択されている場合のみ）
        if show_non_reacted:
            logger.info("Processing non-reacted users")
            non_reacted_user_ids = list(all_members - reacted_users)
            logger.info(f"Found {len(non_reacted_user_ids)} potentially non-reacted users")
            
            # ユーザー情報を一括取得
            users_info = get_users_info(client, non_reacted_user_ids)
            logger.info(f"Retrieved info for {len(users_info)} users")
            
            non_reacted_users = set()
            for user_id in non_reacted_user_ids:
                user_info = users_info.get(user_id, {})
                if not (user_info.get("is_bot", False) or 
                        user_info.get("is_app_user", False) or 
                        user_info.get("deleted", False)):
                    non_reacted_users.add(user_id)
            
            logger.info(f"Found {len(non_reacted_users)} active non-bot users who haven't reacted")

            # 未リアクションユーザーをブロックに追加
            if non_reacted_users:
                non_reacted_mentions = [f"<@{user}>" for user in non_reacted_users]
                chunk_size = 10
                for i in range(0, len(non_reacted_mentions), chunk_size):
                    chunk = non_reacted_mentions[i:i + chunk_size]
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*未リアクションのユーザー* ({len(non_reacted_users)}人中 {i+1}～{min(i+chunk_size, len(non_reacted_mentions))}人目):\n{', '.join(chunk)}"
                        }
                    })

        # 元のメッセージのURLを作成（ワークスペースドメインを動的に取得）
        if workspace_info and workspace_info.get("domain"):
            message_url = f"https://{workspace_info['domain']}.slack.com/archives/{channel_id}/p{message_id.replace('.', '')}"
        else:
            # フォールバック：一般的なSlackのURLフォーマット
            message_url = f"https://slack.com/archives/{channel_id}/p{message_id.replace('.', '')}"

        # 統計情報を追加
        stats_text = f"*統計情報*\n• リアクション済: {len(reacted_users)}人"
        if show_non_reacted:
            stats_text += f"\n• 全メンバー数: {len(all_members)}人\n• 未リアクション: {len(all_members - reacted_users)}人"

        stats_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": stats_text
            }
        }

        # DMを送信する際は、ショートカット実行者のIDを使用
        logger.info(f"Sending final result to shortcut user {shortcut_user_id}")
        try:
            response = client.chat_postMessage(
                channel=shortcut_user_id,  # ショートカット実行者にDMを送信
                text="メッセージへのリアクション状況をまとめました！",
                blocks=[
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
                            "text": f"*元のメッセージ*: <{message_url}>"
                        }
                    },
                    stats_block,
                    {"type": "divider"},
                    *blocks
                ]
            )
            logger.info(f"DM sent successfully to shortcut user {shortcut_user_id} in channel {response.get('channel')}")
        except Exception as e:
            logger.exception(f"Error sending DM to shortcut user {shortcut_user_id}")
            raise

    except Exception as e:
        logger.exception("Error in handle_reaction_options_submission")
        # エラー時もショートカット実行者にDMを送信
        client.chat_postMessage(
            channel=shortcut_user_id,
            text=f"エラーが発生しました: {str(e)}"
        )

def is_bot_user(client, user_id: str) -> bool:
    """ユーザーがBotかどうかを判定する"""
    try:
        user_info = client.users_info(user=user_id)
        return user_info["user"]["is_bot"] or user_info["user"]["is_app_user"]
    except Exception as e:
        logger.warning(f"Failed to check if user {user_id} is bot: {e}")
        return False

# メイン部分も修正
if __name__ == "__main__":
    try:
        logger.info("="*50)
        logger.info(f"Starting {APP_NAME} v{__version__}")
        logger.info("="*50)
        
        # アプリを初期化
        if initialize_app():
            # Socket Mode ハンドラーの初期化
            handler = SocketModeHandler(
                app=app, 
                app_token=os.getenv("SLACK_APP_TOKEN")
            )
            logger.info("⚡️ Bolt app is starting...")
            handler.start()
        else:
            logger.error("Failed to initialize app")
            sys.exit(1)
    except Exception as e:
        logger.exception("Error starting app")
        sys.exit(1)
