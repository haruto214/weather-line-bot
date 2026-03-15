# LINE天気予報通知アプリ（福岡市）｜GitHub Actions × 気象庁JSON × LINE Messaging API

毎朝決まった時刻に、**福岡市（福岡地方）の天気予報**を **LINEグループ**へ自動通知するPythonスクリプトです。  
GitHub Actions のスケジュール実行で、PCを起動しっぱなしにする必要がありません。

## 特徴

- 福岡市（福岡地方）の **今日の天気**を通知
- 天気文を読みやすく整形（例：`晴れのちくもり`）
- 天気マークを **複合表示**（例：`☀️/☁️`）
- 降水確率を **時間帯（6時間区間）**で表示  
  - 朝運用（6:30想定）で **06:00-12:00 / 12:00-18:00 / 18:00-24:00** のみ表示（過去区間は非表示）
  - 「最大%」＋「各時間帯」＋「区切り線」で見やすく表示
- GitHub Actions の定期実行で毎日自動送信（手動実行も可能）

## 仕組み（概要）

1. 気象庁の天気予報JSONを取得（例：福岡県 `400000`）
2. JSONから「福岡地方」の天気文（weathers）と降水確率（pops）を抽出
3. 読みやすい形式に整形（天気文の要約、絵文字、降水ブロック）
4. LINE Messaging API の Push でLINEグループに送信
5. GitHub Actions の schedule で毎日実行（cron は UTC 指定）

## なぜこの構成にしたのか（設計の理由）

このアプリは以下の要件に従って設計しています。  
・完全無料  
・PCを起動しっぱなしにしなくてよい  
・毎日決まった時刻に、LINEグループへ天気を自動通知する  

これらの要件に対して、**GitHub Actions × 気象庁JSON × LINE Messaging API** の組み合わせが、実装・運用コスト・学習コストのバランスが良かったため採用しました。

### 1) 実行基盤：GitHub Actions を選んだ理由
- **サーバー不要で、定期実行（schedule/cron）ができる**ため、PCを付けっぱなしにせず自動実行できます。
- `workflow_dispatch` を併用すると **手動実行もでき、動作確認がしやすい**ため、初心者でも運用が安定します。
- `schedule.cron` は **UTC指定**なので、JSTで動かしたい場合は時差（UTC+9）を考慮して設定します。
  - 例：JST 06:30 に動かしたい → UTC 21:30（前日）なので `30 21 * * *` を設定します。

### 2) 天気データ：気象庁JSON を選んだ理由
- 気象庁サイトで利用されている **天気予報データを JSON で取得でき、地域コード（例：福岡県 400000）で指定できる**ため、実装がシンプルです。
- 取得URLが明確（`https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json`）で、HTTP GET で完結するため、Python初心者でも扱いやすいです。
- `timeSeries` に **天気文（weathers）** と **降水確率（pops + timeDefines）** のような情報がまとまっており、通知メッセージを組み立てやすいです。

### 3) 通知先：LINE Messaging API（Push）を選んだ理由
- LINEの通知を自動化するために、**Botから任意のタイミングで送れる Push メッセージ**を利用しました。
- 送信は `POST /v2/bot/message/push` で行え、宛先（to）に **groupId** を指定することでLINEグループへ通知できます。
- GitHub Actions から実行する場合、トークン（Channel access token）や groupId は **GitHub Secrets で管理**することで、コードに直書きせず安全に運用できます。

### 4) この構成のメリット・デメリット
**メリット**
- サーバー不要で運用でき、実装も「取得→整形→送信」の3ステップで分かりやすい。
- 失敗時は GitHub Actions のログで原因追跡でき、手動実行（workflow_dispatch）で再実行もできる。

**デメリット**
- GitHub Actions の schedule は **UTC基準**であり、JST変換が必要です。
- schedule 実行は混雑状況で遅延する可能性があるため、通知時刻に余裕を持たせる（例：7:00に通知が欲しい場合は6:30実行）などの工夫が必要です。
- 気象庁JSONはWebサイト内部データであり、将来的な仕様変更の可能性があります（その場合はパース処理の調整が必要です）。

## 必要なもの

- GitHubアカウント（GitHub Actions を使うため）
- LINE Developers の Messaging API チャネル
  - Channel access token（長期）
  - groupId（Cから始まるグループID）

## セットアップ

### 1) リポジトリ構成

```text
.
├── main.py
└── .github/
    └── workflows/
        └── weather.yml
```

### 2) GitHub Secrets を設定

GitHub リポジトリの  
`Settings -> Secrets and variables -> Actions -> New repository secret`  
で以下を登録します。

- `LINE_CHANNEL_ACCESS_TOKEN`：チャネルアクセストークン（長期）
- `LINE_GROUP_ID`：送信先のグループID（Cから始まる）

※機密情報なので、コードに直書きしないでください。

### 3) GitHub Actions（workflow）設定

`.github/workflows/weather.yml` 例：

> GitHub Actions の cron は UTC 指定です。  
> 日本時間 6:30 は UTC 21:30（前日）なので `30 21 * * *` を指定します。

```yaml
name: Daily Weather to LINE (Group)

on:
  workflow_dispatch:
  schedule:
    - cron: "30 21 * * *"  # UTC 21:30 = JST 06:30

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install requests

      - name: Run main.py
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_GROUP_ID: ${{ secrets.LINE_GROUP_ID }}
          # 任意（デフォルトは福岡）
          JMA_OFFICE_CODE: "400000"
          TARGET_FORECAST_AREA_NAME: "福岡地方"
          TARGET_TEMP_AREA_NAME: "福岡"
        run: python main.py

```

##  動作確認（手動実行）

1) GitHub の Actions タブを開く  
2) ワークフローを選択  
3) Run workflow を押す  
4) LINEグループに通知が届けばOK  

##  環境変数

スクリプトは以下の環境変数で挙動を変更できます。

・JMA_OFFICE_CODE（デフォルト：400000）  
・TARGET_FORECAST_AREA_NAME（デフォルト：福岡地方）  
・TARGET_TEMP_AREA_NAME（デフォルト：福岡）   
