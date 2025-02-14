# Reaction Indexer

## 概要
Reaction Indexerは、Slackメッセージのリアクション状況を簡単に確認できるツールです。

## 主な機能
- メッセージへのリアクション一覧を表示
- リアクションした人の一覧を表示
- オプションで未リアクションのメンバーも表示可能
- 統計情報の表示（リアクション数、参加者数など）

## インストール方法
1. Slack App Directoryから「Reaction Indexer」を検索
2. 「Slackに追加」ボタンをクリック
3. 必要な権限を確認し、承認
4. Socket Mode用のApp-Level Tokenを生成（管理者のみ）:
   - アプリの設定ページで「Socket Mode」を有効化
   - App-Level Tokenを生成し、ワークスペースに設定

## 使い方
1. リアクション状況を確認したいメッセージの「その他のアクション」（...）をクリック
2. ショートカットメニューから「リアクション一覧を表示」を選択
3. 必要に応じて「未リアクションのユーザーも表示する」オプションを選択
4. 「表示」ボタンをクリックして結果を確認

## プライバシーポリシー
本アプリは以下の情報にのみアクセスします：
- メッセージのリアクション情報
- チャンネルメンバー一覧
- ユーザー表示名

収集した情報は表示目的にのみ使用し、外部への送信や保存は行いません。

## サポート
問題が発生した場合は、[GitHubのIssue](https://github.com/april-knights-dev/slack-reaction-indexer/issues)からご報告ください。

## ライセンス
MIT License

---

# 開発者向け情報

## 開発環境のセットアップ

### 必要条件
- Python 3.8以上
- pip
- Slackワークスペースの管理者権限（開発用）

### インストール手順

1. リポジトリのクローン
```bash
git clone https://github.com/april-knights-dev/slack-reaction-indexer.git
cd slack-reaction-indexer
```

2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

3. 環境変数の設定
`.env`ファイルをプロジェクトのルートディレクトリに作成し、以下の環境変数を設定：
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token
```

### Slack App の設定

1. [Slack API](https://api.slack.com/apps)にアクセスし、新しいアプリを作成
2. 「Socket Mode」を有効化
3. 以下のBot Token Scopesを追加：
   - channels:history
   - channels:read
   - chat:write
   - commands
   - groups:history
   - groups:read
   - reactions:read
   - users:read
   - users:read.email
4. アプリをワークスペースにインストール
5. 必要なトークン類を取得し、`.env`ファイルに設定

### カスタマイズ

#### Slackワークスペース URL の設定
`main.py`内の`message_url`生成部分を自身のワークスペースに合わせて変更：
```python
message_url = f"https://your-workspace.slack.com/archives/{channel_id}/p{message_id.replace('.', '')}"
```

#### レート制限の調整
必要に応じて`RateLimiter`クラスのパラメータを調整：
```python
rate_limiter = RateLimiter(max_requests=10, time_window=60)  # デフォルト: 60秒間に10リクエスト
```

## 開発用コマンド

### アプリの起動
```bash
python main.py
```

### テストの実行
```bash
# TODO: テストを追加予定
```

## コントリビューション

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 技術仕様

- **フレームワーク**: Slack Bolt for Python
- **主要な依存関係**:
  - slack_bolt: Slackアプリケーションフレームワーク
  - python-dotenv: 環境変数管理
  - slack_sdk: Slack API クライアント

## デバッグ

アプリのデバッグログを有効にするには、環境変数に以下を追加：
```bash
SLACK_DEBUG=true
```

## リリース手順

1. バージョン番号を更新 (`__version__` in `main.py`)
2. CHANGELOGを更新
3. コミットしてタグを作成
4. GitHub Releasesを作成
5. 必要に応じてSlack App Directoryの情報を更新
