# Slack Reaction Indexer

Slackのメッセージについたリアクションを集計し、見やすいレポートとしてDMに送信するSlackアプリケーションです。
Botを除外した純粋なメンバーのリアクション状況を把握したり、まだリアクションしていないメンバーを確認したりすることができます。

## 📸 機能概要

*   **メッセージショートカット起動**: 任意のSlackメッセージから直接起動します。
*   **集計オプション**: 未リアクションのユーザーを表示するかどうかを選択できます。
*   **詳細レポート**:
    *   リアクションの種別ごとのカウントとユーザー一覧
    *   誰がリアクションしていないかの一覧（オプション）
    *   Botを除外した正確な参加者数ベースの集計

## 🛠 前提条件

*   Python 3.11+
*   Google Cloud SDK (Cloud Runへのデプロイ用)
*   Slack Appの設定権限

## ⚙️ Slack App の設定

このアプリを動作させるには、Slack APIでアプリを作成し、以下の設定を行う必要があります。

1.  **Create New App**: [Slack API](https://api.slack.com/apps) から `From scratch` でアプリを作成。
2.  **OAuth & Permissions**:
    *   以下の **Bot Token Scopes** を追加します。
        *   `channels:read`: チャンネル情報の取得
        *   `groups:read`: プライベートチャンネル情報の取得
        *   `chat:write`: レポートDMの送信
        *   `reactions:read`: リアクションの取得
        *   `users:read`: ユーザー情報の取得（Bot判定用）
        *   `commands`: ショートカットの実行
    *   アプリをワークスペースにインストールし、`Bot User OAuth Token` (`xoxb-...`) を取得します。
3.  **Basic Information**:
    *   `App Credentials` から `Signing Secret` を取得します。
4.  **Interactivity & Shortcuts**:
    *   Interactivity を **On** に切り替えます。
    *   **Request URL** にデプロイ後のURL + `/slack/events` を設定します（例: `https://your-cloud-run-url.run.app/slack/events`）。
    *   **Shortcuts** セクションで "Create a New Shortcut" をクリックし、以下を設定します。
        *   **Where should this shortcut appear?**: `On messages`
        *   **Name**: `リアクション集計` (任意の表示名)
        *   **Short Description**: メッセージのリアクション状況を表示します
        *   **Callback ID**: `get_reaction_users` (必須: コード内で定義されています)

## 🚀 環境変数の設定

`.env` ファイルを作成するか、Cloud Runの環境変数として以下を設定します。

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
```

## 💻 ローカルでの実行

1.  依存関係のインストール
    ```bash
    pip install -r requirements.txt
    ```

2.  アプリの起動
    ```bash
    python main.py
    ```
    ※ ローカルでSlackからのイベントを受け取るには、ngrokなどのトンネリングツールを使用するか、開発中はSocket Modeを使用するようコードを一時的に変更する必要があります（本番コードはHTTPモード専用です）。

## ☁️ Cloud Run へのデプロイ

Google Cloud Run にデプロイすることで、サーバーレスで安定して稼働させることができます。

1.  gcloud コマンドでデプロイ
    ```bash
    gcloud run deploy slack-reaction-indexer \
      --source . \
      --platform managed \
      --region asia-northeast1 \
      --allow-unauthenticated \
      --set-env-vars SLACK_BOT_TOKEN=xoxb-xxxx,SLACK_SIGNING_SECRET=yyyy
    ```

2.  生成されたURL（例: `https://slack-reaction-indexer-xxxxx-an.a.run.app`）を確認し、Slack App設定画面の **Request URL** に `https://.../slack/events` の形式で設定してください。

## 📝 補足

*   **Botの除外**: 集計において、`is_bot` フラグがTrueのユーザーおよびSlack公式Bot（`USLACKBOT`）は自動的に除外されます。
*   **大規模チャンネル**: 参加者が数千人を超えるチャンネルでは、Slack APIのレート制限により集計に時間がかかる場合があります。

## 📜 License

MIT
