# 概要

slack-reaction-indexerはSlackのメッセージに対するリアクションを取得し、リアクションをしたユーザーの一覧を作成するPythonスクリプトです。このスクリプトはSlackのショートカットを使用して起動します。

## セットアップ

## 環境変数の設定

.envファイルをプロジェクトのルートディレクトリに作成し、以下の環境変数を設定してください。

```bash
SLACK_BOT_TOKEN=あなたのボットトークン
SLACK_SIGNING_SECRET=あなたの署名秘密鍵
SLACK_APP_TOKEN=あなたのアプリトークン
```

## SlackワークスペースのURLの変更

スクリプト内のmessage_urlの`https://aprilknights.slack.com/`をあなたのSlackワークスペースのURLに変更してください。

## 実行方法

以下のコマンドを実行してください。
```python main.py``````

これにより、アプリが起動し、指定したショートカットが実行されると、リアクションをしたユーザーの一覧が作成されます。
