#!/usr/bin/env python3
"""
네이버 언론사 홈(media.naver.com/press/{oid})의 '언론사 주요뉴스' 수집기
- 언론사별 주요뉴스 6개 (통상 텍스트 4 + 사진 2)
- KST 08:00 / 13:00 / 22:30 에 GitHub Actions cron으로 실행
- 결과: data/YYYY-MM-DD/HHMM.json
"""

import json
import re
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))

PRESS_OIDS = {
    # 전국 종합일간지
    "국민일보": "005", "동아일보": "020", "문화일보": "021", "세계일보": "022",
    "조선일보": "023", "중앙일보": "025", "한겨레": "028", "경향신문": "032",
    "서울신문": "081", "한국일보": "469",
    # 경제지·경제 종합매체
    "머니투데이": "008", "매일경제": "009", "서울경제": "011", "파이낸셜뉴스": "014",
    "한국경제": "015", "헤럴드경제": "016", "이데일리": "018", "아시아경제": "277",
    "조선비즈": "366",
    # 통신사
    "연합뉴스": "001", "뉴시스": "003", "뉴스1": "421",
    # 방송사
    "YTN": "052", "SBS": "055", "KBS": "056", "MBN": "057", "MBC": "214",
    "연합뉴스TV": "422", "JTBC": "437", "TV조선": "448", "채널A": "449",
    # 종합 인터넷신문
    "프레시안": "002", "오마이뉴스": "047", "노컷뉴스": "079", "데일리안": "119",
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": "https://media.naver.com/",
}

ARTICLE_RE = re.compile(r"/article/(\d{3})/(\d+)")


def extract_main_news(html: str, oid: str, max_items: int = 6):
    """
    '언론사 주요뉴스' 섹션에서 기사 추출.
    1차: 클래스 기반 선택자 시도
    2차(폴백): '주요뉴스' 헤더가 있는 섹션 내 기사 링크 수집
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen_aids = set()

    def add(a_tag, section_type):
        href = a_tag.get("href", "")
        m = ARTICLE_RE.search(href)
        if not m:
            return
        a_oid, aid = m.group(1), m.group(2)
        if aid in seen_aids:
            return
        # 제목 추출: 전용 클래스 우선, 없으면 a 태그 텍스트
        title_el = a_tag.select_one(
            ".press_news_text, .press_edit_news_text, .press_photo_text, strong, span"
        )
        title = (title_el or a_tag).get_text(" ", strip=True)
        if not title:
            return
        seen_aids.add(aid)
        items.append({
            "rank": len(items) + 1,
            "type": section_type,
            "title": title,
            "url": f"https://n.news.naver.com/article/{a_oid}/{aid}",
            "oid": a_oid,
            "aid": aid,
        })

    # ---- 1차: 알려진 클래스 구조 ----
    # 텍스트 주요뉴스 (상위 4개)
    for a in soup.select(
        "ul.press_news_list a.press_news_link, "
        "div.press_main_news a.press_news_link"
    ):
        if len(items) >= max_items:
            break
        add(a, "headline")

    # 사진 뉴스 (2개)
    for a in soup.select(
        "div.press_photo_news a, "
        "ul.press_photo_list a, "
        "a.press_edit_news_link"
    ):
        if len(items) >= max_items:
            break
        add(a, "photo")

    # ---- 2차 폴백: '주요뉴스' 텍스트가 포함된 섹션에서 수집 ----
    if len(items) < max_items:
        for header in soup.find_all(string=re.compile(r"주요\s*뉴스")):
            section = header.find_parent(["section", "div"])
            hops = 0
            while section and hops < 3 and not section.find_all("a", href=ARTICLE_RE):
                section = section.find_parent(["section", "div"])
                hops += 1
            if not section:
                continue
            for a in section.find_all("a", href=ARTICLE_RE):
                if len(items) >= max_items:
                    break
                add(a, "headline")
            if len(items) >= max_items:
                break

    return items[:max_items]


def crawl_all():
    now = datetime.now(KST)
    result = {
        "collected_at": now.isoformat(),
        "collected_at_kst": now.strftime("%Y-%m-%d %H:%M:%S"),
        "press_count": len(PRESS_OIDS),
        "presses": {},
        "errors": {},
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    for name, oid in PRESS_OIDS.items():
        url = f"https://media.naver.com/press/{oid}"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            news = extract_main_news(resp.text, oid)
            result["presses"][name] = {
                "oid": oid,
                "url": url,
                "news": news,
                "count": len(news),
            }
            if len(news) < 6:
                result["errors"][name] = f"only {len(news)} items parsed"
            print(f"[OK] {name}({oid}): {len(news)} items")
        except Exception as e:
            result["errors"][name] = str(e)
            result["presses"][name] = {"oid": oid, "url": url, "news": [], "count": 0}
            print(f"[FAIL] {name}({oid}): {e}")
        time.sleep(random.uniform(1.0, 2.5))  # 매너 있는 간격

    return result, now


def save(result, now):
    # 08:00 → 0800.json, 13:00 → 1300.json, 22:30 → 2230.json
    # cron 지연을 감안해 가장 가까운 슬롯으로 스냅 (자정 넘김 대비 원형 거리)
    slots = [(8, 0), (13, 0), (22, 30)]
    cur = now.hour * 60 + now.minute

    def circular_dist(s):
        d = abs(s[0] * 60 + s[1] - cur)
        return min(d, 1440 - d)

    slot = min(slots, key=circular_dist)
    fname = f"{slot[0]:02d}{slot[1]:02d}.json"

    # 22:30 실행이 자정을 넘겨 지연된 경우 → 전날 폴더에 귀속
    date = now
    if slot == (22, 30) and cur < 12 * 60:
        date = now - timedelta(days=1)

    date_dir = Path("data") / date.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    path = date_dir / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")
    return path


if __name__ == "__main__":
    result, now = crawl_all()
    save(result, now)
    ok = sum(1 for p in result["presses"].values() if p["count"] > 0)
    print(f"Done: {ok}/{len(PRESS_OIDS)} presses collected, "
          f"{len(result['errors'])} warnings/errors")
