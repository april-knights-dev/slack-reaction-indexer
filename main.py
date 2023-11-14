import os
from datetime import datetime
from os.path import dirname, join

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

load_dotenv(verbose=True)
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# ボットトークンとソケットモードハンドラーを使ってアプリを初期化します
app = App(token=os.getenv("SLACK_BOT_TOKEN"),
          signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
          )
client = WebClient(os.getenv("SLACK_BOT_TOKEN"))

@app.shortcut("get_reaction_users")
def handle_get_reactions(ack, body, client, logger):
    ack()

    message_id = body['message']['ts']
    channel_id = body['channel']['id']
    user_id = body['user']['id']

    try:
        # メッセージに対するリアクションを取得
        response = client.reactions_get(channel=channel_id, timestamp=message_id)
        message = response['message']

        if 'reactions' in message:
            reactions = message['reactions']

            # リアクションをしたユーザーの一覧を作成
            blocks = []
            for reaction in reactions:
                users = reaction['users']
                user_mentions = [f"<@{user}>" for user in users]  # メンション形式に変換
                user_mentions_str = ', '.join(user_mentions)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":{reaction['name']}: (人数: {len(users)}) : {user_mentions_str} "
                    }
                })

            # 元のメッセージのURLを作成
            message_url = f"https://aprilknights.slack.com/archives/{channel_id}/p{message_id.replace('.', '')}"

            # ショートカットを起動したユーザーにDMを送る
            client.chat_postMessage(
                channel=user_id,
                text="メッセージにリアクションしたユーザーを一覧化しました！",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "リアクションしたユーザーの一覧",
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
                    *blocks
                ]
            )
        else:
            client.chat_postMessage(channel=user_id, text="このメッセージにはリアクションがありません。")

    except Exception as e:
        logger.error(f"Error getting reactions: {e}")


# アプリを起動します
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
