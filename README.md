# 🌤️ Daily Weather Briefing

매일 오전 1시, 3개 지역 날씨를 이메일로 자동 발송합니다.

## 지역

| 지역 | 위도 | 경도 |
|------|------|------|
| 경기 김포 고촌 | 37.6089 | 126.7728 |
| 서울 | 37.5665 | 126.9780 |
| 강원 동해 | 37.5244 | 129.1144 |

## 날씨 API

[Open-Meteo](https://open-meteo.com/) — 무료, API 키 불필요

## GitHub Secrets 설정

| Secret | 설명 |
|--------|------|
| `SENDER_EMAIL` | 발신 Gmail 주소 |
| `SENDER_PASSWORD` | Gmail 앱 비밀번호 |
| `RECIPIENT_EMAIL` | 수신 이메일 주소 |

> Gmail → Google 계정 → 보안 → 2단계 인증 ON → **앱 비밀번호** 생성

## 스케줄

```
cron: '0 16 * * *'   →   KST 매일 오전 01:00
```

## 로컬 테스트

```bash
# .env 파일에 Secrets 값 설정 후
export SENDER_EMAIL=xxx@gmail.com
export SENDER_PASSWORD=xxxx
export RECIPIENT_EMAIL=xxx@gmail.com
python src/weather_briefing.py
```
