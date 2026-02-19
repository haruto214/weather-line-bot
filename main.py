import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ====== 設定（環境変数で上書き可能）======
JMA_OFFICE_CODE = os.getenv("JMA_OFFICE_CODE", "400000")  # 福岡県
TARGET_FORECAST_AREA_NAME = os.getenv("TARGET_FORECAST_AREA_NAME", "福岡地方")
TARGET_TEMP_AREA_NAME = os.getenv("TARGET_TEMP_AREA_NAME", "福岡")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")  # ★追加（Cから始まるgroupId）

def fetch_jma_forecast(office_code: str) -> list:
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{office_code}.json"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def pick_area(areas: list, name: str) -> dict:
    for a in areas:
        if a.get("area", {}).get("name") == name:
            return a
    raise ValueError(f"指定した地域名 '{name}' が見つかりませんでした。")

def weather_to_emoji(main_weather: str) -> str:
    """
    メイン天気（晴れ/くもり/雨/雪）から絵文字を決める
    """
    if "晴れ" in main_weather:
        return "☀️"
    if "くもり" in main_weather:
        return "☁️"
    if "雨" in main_weather:
        return "🌧️"
    if "雪" in main_weather:
        return "❄️"
    return "🌤️"

def normalize_weather_text(raw: str) -> str:
    """
    気象庁の天気文を「〇〇のち〇〇」形式へ寄せる（シンプル版）
    例:
      'くもり 昼前から晴れ 所により 朝まで 雨' → 'くもりのち晴れ'
      '晴れ 夕方から くもり' → '晴れのちくもり'
      '雨' → '雨'
    ルール:
      - 文中に出てくる天気語（晴れ/くもり/雨/雪）を出現順に拾う
      - 最初をメイン、次に出た別の天気を「のち」として採用
      - 3つ以上出ても「最初の2つ」だけにする（読みやすさ優先）
    """
    t = raw.replace("　", " ").strip()

    # 天気語の表記ゆれを吸収（曇→くもり）
    t = t.replace("曇り", "くもり").replace("曇", "くもり")

    keywords = ["晴れ", "くもり", "雨", "雪"]
    found = []

    # 出現順に拾う
    for k in keywords:
        pass  # 位置で拾うため後でまとめて処理

    positions = []
    for k in keywords:
        idx = t.find(k)
        if idx != -1:
            positions.append((idx, k))
    positions.sort()

    for _, k in positions:
        if not found or found[-1] != k:
            found.append(k)

    if not found:
        return raw.strip()

    # 最初の2つだけに絞る
    if len(found) == 1:
        return found[0]
    else:
        return f"{found[0]}のち{found[1]}"
        
def build_message(jma_json: list) -> str:
    data0 = jma_json[0]
    publishing_office = data0.get("publishingOffice", "気象庁")
    report_dt = data0.get("reportDatetime", "")

    # 今日の天気（文章）
    ts_weather = data0["timeSeries"][0]
    area_weather = pick_area(ts_weather["areas"], TARGET_FORECAST_AREA_NAME)
    today_weather_text = area_weather["weathers"][0]
    simple_weather = normalize_weather_text(today_weather_text)
    main_weather = simple_weather.split("のち")[0]  # メイン（のち形式でなくてもOK）
    emoji = weather_to_emoji(main_weather)

    # 降水確率（複数値）→ 今日分の最大値を表示
    ts_pop = data0["timeSeries"][1]
    area_pop = pick_area(ts_pop["areas"], TARGET_FORECAST_AREA_NAME)
    pops = area_pop.get("pops", [])
    pop_vals = [int(p) for p in pops if isinstance(p, str) and p.isdigit()]
    pop_max = max(pop_vals) if pop_vals else None

    # 気温（temps: 最低/最高が入ることが多い）
    ts_temp = data0["timeSeries"][2]
    area_temp = pick_area(ts_temp["areas"], TARGET_TEMP_AREA_NAME)
    temps = area_temp.get("temps", [])
    temp_min = temps[0] if len(temps) >= 1 else None
    temp_max = temps[1] if len(temps) >= 2 else None

    # 今日の日付（JSTで固定）
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
    date_str = now_jst.strftime("%-m/%-d(%a)")  # 例: 2/20(Thu) ※Windows互換が心配なら下に置換案あり

    # 英語の曜日を日本語に変換（簡易）
    dow_map = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": "土", "Sun": "日"}
    # %a が英語になる環境用に置換
    if "(" in date_str and ")" in date_str:
        dow = date_str.split("(")[-1].split(")")[0]
        date_str = date_str.replace(dow, dow_map.get(dow, dow))

    # reportDatetime を短く見せる（例: 2026-02-20T05:00:00+09:00 → 05:00）
    report_time = ""
    try:
        report_time = report_dt.split("T")[1][:5]
    except Exception:
        report_time = report_dt

    lines = []
    lines.append(f"{emoji} 福岡市 {date_str}")
    lines.append(f"天気：{simple_weather}")

    lines.append("")  # 空行

    if temp_min is not None and temp_max is not None:
        lines.append(f"気温：{temp_min}℃ / {temp_max}℃")
    if pop_max is not None:
        lines.append(f"降水：最大 {pop_max}%（今日）")

    lines.append("")  # 空行
    lines.append(f"発表：{report_time}（{publishing_office}）")

    return "\n".join(lines)

def send_line_to_group(message: str):
    """
    LINEグループへPush送信（Messaging API）
    """
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_GROUP_ID:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_GROUP_ID を GitHub Secrets に設定してください。")

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": LINE_GROUP_ID,  # ★ここがグループID
        "messages": [{"type": "text", "text": message}],
    }

    r = requests.post(url, headers=headers, json=payload, timeout=10)
    r.raise_for_status()

def main():
    jma = fetch_jma_forecast(JMA_OFFICE_CODE)
    msg = build_message(jma)
    send_line_to_group(msg)

if __name__ == "__main__":
    main()
