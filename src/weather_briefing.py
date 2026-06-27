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
    {"name": "경기 김포 고촌",  "lat": 37.6089, "lon": 126.7728, "emoji": "🏘️", "naver_url": "https://weather.naver.com/today/02570253"},
    {"name": "서울 여의도",     "lat": 37.5219, "lon": 126.9245, "emoji": "🏙️", "naver_url": "https://weather.naver.com/today/09560110"},
    {"name": "강원 동해",       "lat": 37.5244, "lon": 129.1144, "emoji": "🌊", "naver_url": "https://weather.naver.com/today/01170101"},
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
# 이메일 HTML 생성 (table 기반 - 이메일 클라이언트 호환)
# ────────────────────────────────────────────────────────────

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

    today_max      = dly["temperature_2m_max"][0]
    today_min      = dly["temperature_2m_min"][0]
    today_rain_pct = dly["precipitation_probability_max"][0]
    sunrise        = dly["sunrise"][0].split("T")[1]
    sunset         = dly["sunset"][0].split("T")[1]

    tmr_max  = dly["temperature_2m_max"][1]
    tmr_min  = dly["temperature_2m_min"][1]
    tmr_rain = dly["precipitation_probability_max"][1]
    tmr_desc, tmr_emoji = get_wmo(dly["weather_code"][1])

    rain_warn = ""
    if today_rain_pct >= 50:
        rain_warn = ' &nbsp;<span style="color:#c0392b;font-weight:bold;">☔ 우산 챙기세요!</span>'
    elif today_rain_pct >= 30:
        rain_warn = ' &nbsp;<span style="color:#e67e22;">⚠️ 우산 대기</span>'

    tmr_rain_note = f'<span style="color:#c0392b;font-weight:bold;">☔ 우산 필요</span>' if tmr_rain >= 50 else f"{tmr_rain}%"

    # 시간대별 행
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
            rp_color = "#c0392b" if rp >= 50 else "#2c3e50"
            rp_weight = "bold" if rp >= 50 else "normal"
            bg = "#fef9f0" if slot % 2 == 0 else "#ffffff"
            hour_rows += f"""
                <tr style="background:{bg};">
                  <td style="padding:8px 12px;font-weight:bold;color:#2c3e50;width:60px;">{slot:02d}시</td>
                  <td style="padding:8px 12px;color:#34495e;">{emoji} {desc}</td>
                  <td style="padding:8px 12px;text-align:center;color:#2c3e50;">{temps[idx]:.0f}°C</td>
                  <td style="padding:8px 12px;text-align:center;color:{rp_color};font-weight:{rp_weight};">{rp}%</td>
                </tr>"""

    return f"""
    <!-- 지역 카드 -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#ffffff;border-radius:8px;margin-bottom:16px;
                  border:1px solid #e0e6ed;overflow:hidden;">
      <!-- 지역 제목 -->
      <tr>
        <td style="background:#1a5276;padding:14px 20px;">
          <a href="{loc['naver_url']}" target="_blank" style="color:#ffffff;font-size:17px;font-weight:bold;text-decoration:none;">
            {loc['emoji']} {loc['name']} &nbsp;<span style="font-size:12px;opacity:0.75;">↗ 네이버 날씨</span>
          </a>
        </td>
      </tr>

      <!-- 요약 4칸 -->
      <tr>
        <td style="padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="50%" style="padding:14px 20px;border-right:1px solid #eaecee;border-bottom:1px solid #eaecee;vertical-align:top;">
                <div style="font-size:11px;color:#7f8c8d;margin-bottom:4px;">현재 날씨</div>
                <div style="font-size:20px;font-weight:bold;color:#1a252f;">{cur_emoji} {cur_desc}</div>
                <div style="font-size:13px;color:#566573;margin-top:3px;">{cur_temp:.1f}°C &nbsp;(체감 {feels:.1f}°C)</div>
              </td>
              <td width="50%" style="padding:14px 20px;border-bottom:1px solid #eaecee;vertical-align:top;">
                <div style="font-size:11px;color:#7f8c8d;margin-bottom:4px;">최저 / 최고</div>
                <div style="font-size:20px;font-weight:bold;color:#1a252f;">{today_min:.0f}°C / {today_max:.0f}°C</div>
                <div style="font-size:13px;color:#566573;margin-top:3px;">강수 확률 {today_rain_pct}%{rain_warn}</div>
              </td>
            </tr>
            <tr>
              <td width="50%" style="padding:14px 20px;border-right:1px solid #eaecee;vertical-align:top;">
                <div style="font-size:11px;color:#7f8c8d;margin-bottom:4px;">습도 / 바람</div>
                <div style="font-size:20px;font-weight:bold;color:#1a252f;">{humidity}%</div>
                <div style="font-size:13px;color:#566573;margin-top:3px;">{wind_dir}풍 {wind_spd:.1f} m/s</div>
              </td>
              <td width="50%" style="padding:14px 20px;vertical-align:top;">
                <div style="font-size:11px;color:#7f8c8d;margin-bottom:4px;">일출 / 일몰</div>
                <div style="font-size:20px;font-weight:bold;color:#1a252f;">🌅 {sunrise}</div>
                <div style="font-size:13px;color:#566573;margin-top:3px;">🌇 {sunset}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- 시간대별 예보 테이블 -->
      <tr>
        <td style="padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr style="background:#d6eaf8;">
              <th style="padding:9px 12px;text-align:left;font-size:12px;color:#1a5276;font-weight:bold;width:60px;">시간</th>
              <th style="padding:9px 12px;text-align:left;font-size:12px;color:#1a5276;font-weight:bold;">날씨</th>
              <th style="padding:9px 12px;text-align:center;font-size:12px;color:#1a5276;font-weight:bold;">기온</th>
              <th style="padding:9px 12px;text-align:center;font-size:12px;color:#1a5276;font-weight:bold;">강수 확률</th>
            </tr>
            {hour_rows}
          </table>
        </td>
      </tr>

      <!-- 내일 예보 -->
      <tr>
        <td style="background:#fef9e7;padding:12px 20px;border-top:1px solid #f9e79f;">
          <span style="font-size:13px;color:#7d6608;font-weight:bold;">내일 예보</span>
          <span style="font-size:13px;color:#5d4037;">
            &nbsp; {tmr_emoji} {tmr_desc} &nbsp;|&nbsp;
            최저 {tmr_min:.0f}°C / 최고 {tmr_max:.0f}°C &nbsp;|&nbsp;
            강수 확률 {tmr_rain_note}
          </a>
        </td>
      </tr>
    </table>"""


def build_html(cards: str, date_str: str, weekday: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f0f3f4;font-family:'Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f3f4;">
  <tr>
    <td align="center" style="padding:24px 16px;">

      <!-- 최대 너비 래퍼 -->
      <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">

        <!-- 헤더 -->
        <tr>
          <td style="background:#1a5276;border-radius:8px 8px 0 0;padding:24px 28px;">
            <div style="color:#ffffff;font-size:22px;font-weight:bold;margin-bottom:4px;">
              🌤️ 오늘의 날씨 브리핑
            </div>
            <div style="color:#aed6f1;font-size:13px;">
              {date_str} ({weekday}) &nbsp;·&nbsp; Open-Meteo 기반
            </div>
          </td>
        </tr>

        <!-- 본문 배경 -->
        <tr>
          <td style="background:#f0f3f4;padding:16px 0;">
            {cards}
          </td>
        </tr>

        <!-- 푸터 -->
        <tr>
          <td style="background:#eaecee;border-radius:0 0 8px 8px;
                     padding:14px 28px;text-align:center;
                     font-size:11px;color:#95a5a6;">
            자동 발송 · Daily Weather Briefing · Open-Meteo API
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""


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