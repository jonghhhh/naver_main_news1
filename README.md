# 네이버 언론사 주요뉴스 수집기

`media.naver.com/press/{oid}` 의 "언론사 주요뉴스" (텍스트 4 + 사진 2 = 6건)를
KST 08:00 / 13:00 / 22:30 에 수집해 JSON으로 저장합니다. 35개 언론사 대상.

## 저장 구조

```
data/
  2026-07-18/
    0800.json
    1300.json
    2230.json
```

각 JSON 스키마:

```json
{
  "collected_at": "2026-07-18T08:03:12+09:00",
  "presses": {
    "한겨레": {
      "oid": "028",
      "url": "https://media.naver.com/press/028",
      "count": 6,
      "news": [
        {"rank": 1, "type": "headline", "title": "...",
         "url": "https://n.news.naver.com/article/028/0002700000",
         "oid": "028", "aid": "0002700000"}
      ]
    }
  },
  "errors": {}
}
```

## 설치

1. GitHub에 새 repo 생성 (private 권장) 후 이 파일들 push
2. Actions 탭에서 workflow 활성화 확인
3. `workflow_dispatch`로 수동 1회 실행하여 셀렉터가 실제 페이지 구조와 맞는지 확인
   - `errors`에 "only N items parsed"가 다수 뜨면 `extract_main_news()`의
     CSS 선택자를 실제 HTML에 맞게 수정 (브라우저 개발자도구로 확인)

## 주의사항

- **GitHub Actions cron은 정시에 안 뜹니다.** 보통 3~15분, 혼잡 시간대엔 그 이상
  지연됩니다. 저장 시 가장 가까운 슬롯(0800/1300/2230)으로 파일명을 스냅하므로
  분석에는 문제없지만, "정각 스냅샷"이 연구 설계상 중요하면 self-hosted runner나
  아래 GAS 방식을 병행하세요.
- 네이버가 GitHub Actions IP 대역을 차단할 가능성이 있습니다. 403이 반복되면
  (a) User-Agent/헤더 조정, (b) self-hosted runner(연구실 서버·DigitalOcean),
  (c) 프록시 사용을 검토하세요. DigitalOcean 서버가 이미 있다면 그쪽 crontab이
  가장 안정적입니다:
  `0 8,13 * * * python3 /path/crawl_press_news.py` + `30 22 * * *` (KST 서버 기준)
- robots.txt 및 이용약관 고려: 학술 목적, 낮은 빈도(하루 3회, 요청 간 1~2.5초
  간격)로 설계했습니다.

## Google Apps Script는?

가능하지만 비추천:
- GAS에는 HTML 파서가 없어 정규식으로 파싱해야 함 (네이버 마크업 변경에 취약)
- 시간 기반 트리거는 ±15분 오차 허용 범위로만 지정 가능 (22:30 같은 정각 불가)
- UrlFetchApp이 네이버에서 차단되는 경우가 잦음
- 장점은 Sheets/Drive 저장이 쉽다는 것뿐인데, GitHub repo 저장이 오히려
  버전 이력 + 재현가능성 면에서 연구용으로 우수

필요하면 GitHub Actions에서 수집 후 Google Sheets API로 동시 기록하는
하이브리드도 가능.
