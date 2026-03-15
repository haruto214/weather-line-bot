# LINE天気予報通知アプリ（福岡市）｜GitHub Actions × 気象庁JSON × LINE Messaging API

毎朝決まった時刻に、**福岡市（福岡地方）の天気予報**を **LINEグループ**へ自動通知するPythonスクリプトです。  
GitHub Actions のスケジュール実行で、PCを起動しっぱなしにする必要がありません。

---

## 特徴

- 福岡市（福岡地方）の **今日の天気**を通知
- 天気文を読みやすく整形（例：`晴れのちくもり`）
- 天気マークを **複合表示**（例：`☀️/☁️`）
- 降水確率を **時間帯（6時間区間）**で表示  
  - 朝運用（6:30想定）で **06:00-12:00 / 12:00-18:00 / 18:00-24:00** のみ表示（過去区間は非表示）
  - 「最大%」＋「各時間帯」＋「区切り線」で見やすく表示
- GitHub Actions の定期実行で毎日自動送信（手動実行も可能）

---

## 仕組み（概要）

1. 気象庁の天気予報JSONを取得（例：福岡県 `400000`）
2. JSONから「福岡地方」の天気文（weathers）と降水確率（pops）を抽出
3. 読みやすい形式に整形（天気文の要約、絵文字、降水ブロック）
4. LINE Messaging API の Push でLINEグループに送信
5. GitHub Actions の schedule で毎日実行（cron は UTC 指定）

---

## 必要なもの

- GitHubアカウント（GitHub Actions を使うため）
- LINE Developers の Messaging API チャネル
  - Channel access token（長期）
  - groupId（Cから始まるグループID）

---

## セットアップ

### 1) リポジトリ構成
.
├── main.py  
└── .github/  
      └── workflows/  
           └── weather.yml  

---

### 2) GitHub Secrets を設定

GitHub リポジトリの  
`Settings -> Secrets and variables -> Actions -> New repository secret`  
で以下を登録します。

- `LINE_CHANNEL_ACCESS_TOKEN`：チャネルアクセストークン（長期）
- `LINE_GROUP_ID`：送信先のグループID（Cから始まる）

※機密情報なので、コードに直書きしないでください。

---

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

---

##  動作確認（手動実行）

1) GitHub の Actions タブを開く  
2) ワークフローを選択  
3) Run workflow を押す  
4) LINEグループに通知が届けばOK  

---

##  環境変数

スクリプトは以下の環境変数で挙動を変更できます。

JMA_OFFICE_CODE（デフォルト：400000）  
TARGET_FORECAST_AREA_NAME（デフォルト：福岡地方）  
TARGET_TEMP_AREA_NAME（デフォルト：福岡）  

---

##　注意点

・気象庁のJSONはWebサイト内部で使われているデータであり、仕様変更の可能性があります。  
・GitHub Actions の schedule 実行は、混雑状況により数分程度遅延することがあります。  
・LINE送信は Messaging API の Push を利用します。  

---
