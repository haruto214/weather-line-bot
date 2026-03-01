import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ====== 設定（環境変数で上書き可能）======
JMA_OFFICE_CODE = os.getenv("JMA_OFFICE_CODE", "400000")  # 福岡県
TARGET_FORECAST_AREA_NAME = os.getenv("TARGET_FORECAST_AREA_NAME", "福岡地方")
TARGET_TEMP_AREA_NAME = os.getenv("TARGET_TEMP_AREA_NAME", "福岡")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")  # Cから始まるgroupId


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
    """メイン天気（晴れ/くもり/雨/雪）から絵文字を決める"""
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
    """
    t = raw.replace("　", " ").strip()
    t = t.replace("曇り", "くもり").replace("曇", "くもり")

    keywords = ["晴れ", "くもり", "雨", "雪"]
    positions = []
    for k in keywords:
        idx = t.find(k)
        if idx != -1:
            positions.append((idx, k))
    positions.sort()

    found = []
    for _, k in positions:
        if not found or found[-1] != k:
            found.append(k)

    if not found:
        return raw.strip()
    if len(found) == 1:
        return found[0]
    return f"{found[0]}のち{found[1]}"


def pops_fixed_buckets_today(ts_pop: dict, area_name: str, now_jst: datetime) -> dict[str, int | None]:
    """
    気象庁の降水確率 timeSeries[1] から「今日」の分だけを集め、
    00-06 / 06-12 / 12-18 / 18-24 の4区間に当てはめる。
    取れない区間は None のまま。
    
    ※ timeSeries[1] は発表時刻によって要素数・含む時間帯が変わるため、欠ける区間があり得る。
    """
    area_pop = pick_area(ts_pop["areas"], area_name)
    pops = area_pop.get("pops", [])
    time_defines = ts_pop.get("timeDefines", [])

    today = now_jst.date()

    buckets: dict[str, int | None] = {
        "00-06": None,
        "06-12": None,
        "12-18": None,
        "18-24": None,
    }

    # timeDefinesをdatetimeに
    tds = []
    for tdef in time_defines:
        try:
            tds.append(datetime.fromisoformat(tdef))
        except Exception:
            tds.append(None)

    # 区間: tds[i]～tds[i+1] に pops[i]
    for i in range(min(len(pops), len(tds) - 1)):
        start = tds[i]
        end = tds[i + 1]
        p = pops[i]

        if start is None or end is None:
            continue
        if not (isinstance(p, str) and p.isdigit()):
            continue

        # 今日の区間だけ
        if start.date() != today:
            continue

        sh = start.strftime("%H")
        eh = end.strftime("%H")
        if eh == "00":
            eh = "24"

        key = f"{sh}-{eh}"
        if key in buckets:
            buckets[key] = int(p)

    return buckets


def format_buckets_line(buckets: dict[str, int | None]) -> tuple[str, int | None]:
    """
    4区間を必ず並べて表示。
    例: '00-06 --% / 06-12 20% / 12-18 10% / 18-24 0%'（最大20%）
    """
    order = ["00-06", "06-12", "12-18", "18-24"]
    parts = []
    vals = []
    for k in order:
        v = buckets.get(k)
        if v is None:
            parts.append(f"{k} --%")
        else:
            parts.append(f"{k} {v}%")
            vals.append(v)
    max_pop = max(vals) if vals else None
    return " / ".join(parts), max_pop


def build_message(jma_json: list) -> str:
    data0 = jma_json[0]
    publishing_office = data0.get("publishingOffice", "気象庁")
    report_dt = data0.get("reportDatetime", "")

    # JST固定
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))

    # 今日の天気（文章）
    ts_weather = data0["timeSeries"][0]
    area_weather = pick_area(ts_weather["areas"], TARGET_FORECAST_AREA_NAME)
    today_weather_text = area_weather["weathers"][0]
    simple_weather = normalize_weather_text(today_weather_text)
    main_weather = simple_weather.split("のち")[0]
    emoji = weather_to_emoji(main_weather)

    # 今日の降水（4区間固定で表示）
    ts_pop = data0["timeSeries"][1]
    buckets = pops_fixed_buckets_today(ts_pop, TARGET_FORECAST_AREA_NAME, now_jst)
    pop_block, pop_max = format_buckets_line(buckets)
    lines.append(pop_block)

    # 気温
    ts_temp = data0["timeSeries"][2]
    area_temp = pick_area(ts_temp["areas"], TARGET_TEMP_AREA_NAME)
    temps = area_temp.get("temps", [])
    temp_min = temps[0] if len(temps) >= 1 else None
    temp_max = temps[1] if len(temps) >= 2 else None

    # 日付文字列（JST）
    date_str = now_jst.strftime("%-m/%-d(%a)")
    dow_map = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": "土", "Sun": "日"}
    if "(" in date_str and ")" in date_str:
        dow = date_str.split("(")[-1].split(")")[0]
        date_str = date_str.replace(dow, dow_map.get(dow, dow))

    # 発表時刻
    report_time = ""
    try:
        report_time = report_dt.split("T")[1][:5]
    except Exception:
        report_time = report_dt

    lines = []
    lines.append(f"{emoji} 福岡市 {date_str}")
    lines.append(f"天気：{simple_weather}")
    lines.append("")

    if temp_min is not None and temp_max is not None:
        lines.append(f"気温：{temp_min}℃ / {temp_max}℃")

    # 今日の降水（必ず4区間）
    if pop_max is None:
        lines.append(f"降水：{pop_line}")
    else:
        lines.append(f"降水：{pop_line}（最大{pop_max}%）")

    lines.append("")
    lines.append(f"発表：{report_time}（{publishing_office}）")

    return "\n".join(lines)


def send_line_to_group(message: str):
    """LINEグループへPush送信"""
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_GROUP_ID:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_GROUP_ID を設定してください。")

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": LINE_GROUP_ID,
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
