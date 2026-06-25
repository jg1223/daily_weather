import urllib.request
import urllib.parse
import json
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))

LOCATIONS = [
    {"name": "경기 김포 고촌",  "lat": 37.6089, "lon": 126.7728, "emoji": "🏘️"},
    {"name": "서울",            "lat": 37.5665, "lon": 126.9780, "emoji": "🏙️"},
    {"name": "강원 동해",       "lat": 37.5244, "lon": 129.1144, "emoji": "🌊"},
]

WMO_CODE = {
    0:  ("맑음",        "☀️"),
    1:  ("대체로 맑음",  "🌤️"),
    2:  ("구름 조금",   "⛅"),
    3:  ("흐림",        "☁️"),
    45: ("안개",        "🌫️"),
    48: ("안개",        "🌫️"),
    51: ("이슬비",      "🌦️"),
    53: ("이슬비",      "🌦️"),
    55: ("이슬비",      "🌦️"),
    61: ("비",          "🌧️"),
    63: ("비",          "🌧️"),
    65: ("강한 비",     "🌧️"),
    71: ("눈",          "❄️"),
    73: ("눈",          "❄️"),
    75: ("강한 눈",     "❄️"),
    77: ("눈보라",      "🌨️"),
    80: ("소나기",      "🌦️"),
    81: ("소나기",      "🌦️"),
    82: ("강한 소나기", "⛈️"),
    85: ("눈소나기",    "🌨️"),
    86: ("눈소나기",    "🌨️"),
    95: ("뇌우",        "⛈️"),
    96: ("뇌우+우박",   "⛈️"),
    99: ("뇌우+우박",   "⛈️"),
}

HOUR_SLOTS = [6, 9, 12, 15, 18, 21]

# ────────────────────────────────────────────────────────────
# Open-Meteo API 호출
# ────────────────────────────────────────────────────────────
def fetch_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude":              lat,
        "longitude":             lon,
        "timezone":              "Asia/Seoul",
        "current":               "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
        "hourly":                "temperature_2m,precipitation_probability,weather_code,relative_humidity_2m",
        "daily":                 "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "forecast_days":         2,
        "wind_speed_unit":       "ms",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def wind_direction_str(deg: float) -> str:
    dirs = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동",
            "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"]
    return dirs[round(deg / 22.5) % 16]


def get_wmo(code: int):
    return WMO_CODE.get(code, ("알 수 없음", "❓"))


# ────────────────────────────────────────────────────────────
# HTML 이메일 생성
# ────────────────────────────────────────────────────────────
STYLE = """
<style>
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
         background:#f0f4f8; margin:0; padding:20px; color:#1a202c; }
  .wrap { max-width:680px; margin:0 auto; }
  .header { background:linear-gradient(135deg,#1e3a5f,#2b6cb0);
            color:#fff; border-radius:12px 12px 0 0; padding:24px 28px; }
  .header h1 { margin:0 0 4px; font-size:22px; }
  .header p  { margin:0; font-size:13px; opacity:.8; }
  .card { background:#fff; border-radius:8px; padding:20px 24px;
          margin:12px 0; box-shadow:0 1px 3px rgba(0,0,0,.08); }
  .loc-title { font-size:17px; font-weight:700; margin:0 0 14px;
               border-bottom:2px solid #ebf4ff; padding-bottom:8px; }
  .summary-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }
  .s-item { background:#f7fafc; border-radius:6px; padding:10px 12px; }
  .s-label { font-size:11px; color:#718096; margin-bottom:3px; }
  .s-value { font-size:18px; font-weight:700; }
  .s-sub   { font-size:12px; color:#4a5568; margin-top:2px; }
  table.hourly { width:100%; border-collapse:collapse; margin-top:14px; font-size:13px; }
  table.hourly th { background:#ebf8ff; color:#2c5282; padding:6px 8px;
                    text-align:center; font-weight:600; }
  table.hourly td { padding:7px 8px; text-align:center; border-bottom:1px solid #f0f0f0; }
  table.hourly tr:last-child td { border-bottom:none; }
  .tomorrow { background:#fffbf0; border:1px solid #fbd38d; border-radius:8px;
              padding:12px 16px; margin-top:14px; font-size:13px; }
  .tomorrow strong { color:#c05621; }
  .footer { text-align:center; font-size:11px; color:#a0aec0; padding:16px; }
  .rain-badge { display:inline-block; background:#ebf8ff; color:#2b6cb0;
                border-radius:12px; font-size:11px; padding:2px 8px; margin-left:6px; }
  .rain-warn { color:#c53030; font-weight:600; }
</style>
"""

def build_location_card(loc: dict, data: dict, today: str) -> str:
    cur  = data["current"]
    hrly = data["hourly"]
    dly  = data["daily"]

    cur_temp  = cur["temperature_2m"]
    feels     = cur["apparent_temperature"]
    humidity  = cur["relative_humidity_2m"]
    wind_spd  = cur["wind_speed_10m"]
    wind_dir  = wind_direction_str(cur["wind_direction_10m"])
    cur_desc, cur_emoji = get_wmo(cur["weather_code"])

    today_max = dly["temperature_2m_max"][0]
    today_min = dly["temperature_2m_min"][0]
    today_rain_pct = dly["precipitation_probability_max"][0]
    sunrise   = dly["sunrise"][0].split("T")[1]
    sunset    = dly["sunset"][0].split("T")[1]

    tmr_max  = dly["temperature_2m_max"][1]
    tmr_min  = dly["temperature_2m_min"][1]
    tmr_rain = dly["precipitation_probability_max"][1]
    tmr_desc, tmr_emoji = get_wmo(dly["weather_code"][1])

    rain_warn = ""
    if today_rain_pct >= 50:
        rain_warn = f'<span class="rain-warn"> ☔ 우산 챙기세요!</span>'
    elif today_rain_pct >= 30:
        rain_warn = f'<span class="rain-badge">우산 대기</span>'

    # 시간대별 예보 (6·9·12·15·18·21시)
    times  = hrly["time"]
    temps  = hrly["temperature_2m"]
    rains  = hrly["precipitation_probability"]
    wcodes = hrly["weather_code"]

    hour_rows = ""
    for slot in HOUR_SLOTS:
        target = f"{today}T{slot:02d}:00"
        if target in times:
            idx = times.index(target)
            desc, emoji = get_wmo(wcodes[idx])
            rp = rains[idx] if rains[idx] is not None else 0
            rp_style = ' style="color:#c53030;font-weight:600"' if rp >= 50 else ""
            hour_rows += f"""
            <tr>
              <td><b>{slot:02d}시</b></td>
              <td>{emoji} {desc}</td>
              <td>{temps[idx]:.0f}°C</td>
              <td{rp_style}>{rp}%</td>
            </tr>"""

    tmr_rain_note = f'<span class="rain-warn">☔ 우산 필요</span>' if tmr_rain >= 50 else f"{tmr_rain}%"

    return f"""
    <div class="card">
      <div class="loc-title">{loc["emoji"]} {loc["name"]}</div>

      <div class="summary-grid">
        <div class="s-item">
          <div class="s-label">현재 날씨</div>
          <div class="s-value">{cur_emoji} {cur_desc}</div>
          <div class="s-sub">{cur_temp:.1f}°C &nbsp;(체감 {feels:.1f}°C)</div>
        </div>
        <div class="s-item">
          <div class="s-label">최저 / 최고</div>
          <div class="s-value">{today_min:.0f}°C / {today_max:.0f}°C</div>
          <div class="s-sub">강수 확률 {today_rain_pct}%{rain_warn}</div>
        </div>
        <div class="s-item">
          <div class="s-label">습도 / 바람</div>
          <div class="s-value">{humidity}%</div>
          <div class="s-sub">{wind_dir}풍 {wind_spd:.1f} m/s</div>
        </div>
        <div class="s-item">
          <div class="s-label">일출 / 일몰</div>
          <div class="s-value">🌅 {sunrise}</div>
          <div class="s-sub">🌇 {sunset}</div>
        </div>
      </div>

      <table class="hourly">
        <tr>
          <th>시간</th><th>날씨</th><th>기온</th><th>강수 확률</th>
        </tr>
        {hour_rows}
      </table>

      <div class="tomorrow">
        <strong>내일 예보</strong> &nbsp;
        {tmr_emoji} {tmr_desc} &nbsp;|&nbsp;
        최저 {tmr_min:.0f}°C / 최고 {tmr_max:.0f}°C &nbsp;|&nbsp;
        강수 확률 {tmr_rain_note}
      </div>
    </div>"""


def build_html(cards: str, date_str: str, weekday: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8">{STYLE}</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🌤️ 오늘의 날씨 브리핑</h1>
    <p>{date_str} ({weekday}) &nbsp;·&nbsp; Open-Meteo 기반</p>
  </div>
  {cards}
  <div class="footer">
    자동 발송 · Daily Weather Briefing · Open-Meteo API
  </div>
</div>
</body></html>"""


# ────────────────────────────────────────────────────────────
# 이메일 발송
# ────────────────────────────────────────────────────────────
def send_email(subject: str, html_body: str):
    sender    = os.environ["SENDER_EMAIL"]
    password  = os.environ["SENDER_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, recipient, msg.as_string())
    print(f"✅ 발송 완료 → {recipient}")


# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────
def main():
    now      = datetime.now(KST)
    today    = now.strftime("%Y-%m-%d")
    date_str = now.strftime("%Y년 %m월 %d일")
    weekday  = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    all_cards = ""
    for loc in LOCATIONS:
        print(f"  🔍 {loc['name']} 날씨 조회 중...")
        data = fetch_weather(loc["lat"], loc["lon"])
        all_cards += build_location_card(loc, data, today)

    html = build_html(all_cards, date_str, weekday)
    subject = f"[날씨] {date_str}({weekday}) · 김포·서울·동해"

    send_email(subject, html)


if __name__ == "__main__":
    main()
