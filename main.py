import os
import requests
from datetime import datetime

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

def build_message(jma_json: list) -> str:
    data0 = jma_json[0]
    publishing_office = data0.get("publishingOffice", "気象庁")
    report_dt = data0.get("reportDatetime", "")

    ts_weather = data0["timeSeries"][0]
    area_weather = pick_area(ts_weather["areas"], TARGET_FORECAST_AREA_NAME)
    today_weather_text = area_weather["weathers"][0]

    ts_pop = data0["timeSeries"][1]
    area_pop = pick_area(ts_pop["areas"], TARGET_FORECAST_AREA_NAME)
    pops = area_pop.get("pops", [])
    pop_vals = [int(p) for p in pops if p.isdigit()]
    pop_max = max(pop_vals) if pop_vals else None

    ts_temp = data0["timeSeries"][2]
    area_temp = pick_area(ts_temp["areas"], TARGET_TEMP_AREA_NAME)
    temps = area_temp.get("temps", [])
    temp_min = temps[0] if len(temps) >= 1 else None
    temp_max = temps[1] if len(temps) >= 2 else None

    today = datetime.now().strftime("%Y/%m/%d")

    lines = []
    lines.append(f"【福岡市（福岡地方）の天気】{today}")
    lines.append(f"天気：{today_weather_text}")
    if temp_min is not None and temp_max is not None:
        lines.append(f"気温：{temp_min}℃ / {temp_max}℃")
    if pop_max is not None:
        lines.append(f"降水確率：最大 {pop_max}%（今日）")
    lines.append("")
    lines.append(f"発表：{publishing_office}")
    lines.append(f"時刻：{report_dt}")
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
