"""Douyin/1688 product intelligence collector pipeline.

Pipeline:
source -> playwright collector -> parser -> storage -> cleaning -> scoring output
"""

from __future__ import annotations

import random
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from playwright.sync_api import Browser, Page, Playwright, sync_playwright


@dataclass
class ProductRaw:
    product_id: str | None
    title: str
    price: float | None
    sales_estimate: int | None
    video_count: int | None
    likes: int | None
    comments: int | None
    video_url: str | None
    source: str
    created_at: str


class ProductStore:
    def __init__(self, db_path: str = "products.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT,
                    title TEXT NOT NULL,
                    price REAL,
                    sales_estimate INTEGER,
                    video_count INTEGER,
                    likes INTEGER,
                    comments INTEGER,
                    video_url TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_products_title_source
                ON products_raw(title, source)
                """
            )

    def exists(self, title: str, source: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM products_raw WHERE title = ? AND source = ? LIMIT 1",
                (title, source),
            ).fetchone()
        return row is not None

    def insert_many(self, items: Iterable[ProductRaw]) -> int:
        saved = 0
        with self._conn() as conn:
            for item in items:
                if self.exists(item.title, item.source):
                    continue
                conn.execute(
                    """
                    INSERT INTO products_raw (
                        product_id, title, price, sales_estimate, video_count,
                        likes, comments, video_url, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.product_id,
                        item.title,
                        item.price,
                        item.sales_estimate,
                        item.video_count,
                        item.likes,
                        item.comments,
                        item.video_url,
                        item.source,
                        item.created_at,
                    ),
                )
                saved += 1
        return saved


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def parse_number(text: str | None) -> int | None:
    if not text:
        return None
    text = text.strip().lower().replace(",", "")
    matched = re.search(r"(\d+(?:\.\d+)?)", text)
    if not matched:
        return None
    value = float(matched.group(1))
    if "w" in text:
        value *= 10_000
    elif "k" in text:
        value *= 1_000
    return int(value)


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    matched = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(matched.group(1)) if matched else None


def start_browser(headless: bool = True) -> tuple[Playwright, Browser, Page]:
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    return p, browser, page


def human_pause(min_s: float = 1.5, max_s: float = 4.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def open_douyin_search(page: Page, keyword: str) -> None:
    page.goto(f"https://www.douyin.com/search/{keyword}", wait_until="domcontentloaded")
    human_pause(3, 6)


def scroll_page(page: Page, times: int = 10) -> None:
    for _ in range(times):
        page.mouse.wheel(0, random.randint(1000, 2800))
        human_pause(2, 5)


def extract_douyin_products(page: Page, limit: int = 30) -> list[ProductRaw]:
    cards = page.locator("div[data-e2e='search-result-item']")
    total = min(cards.count(), limit)
    results: list[ProductRaw] = []

    for idx in range(total):
        card = cards.nth(idx)
        title = clean_title(card.inner_text(timeout=1500))
        href = card.locator("a").first.get_attribute("href")
        full_url = None if not href else (href if href.startswith("http") else f"https:{href}")

        likes_text = card.locator("text=/赞|点赞/").first.text_content()
        comments_text = card.locator("text=/评论/").first.text_content()

        results.append(
            ProductRaw(
                product_id=None,
                title=title,
                price=None,
                sales_estimate=None,
                video_count=None,
                likes=parse_number(likes_text),
                comments=parse_number(comments_text),
                video_url=full_url,
                source="douyin_search",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    return results


def collect_keyword(keyword: str, db_path: str = "products.db", headless: bool = True) -> int:
    store = ProductStore(db_path)
    p, browser, page = start_browser(headless=headless)
    try:
        open_douyin_search(page, keyword)
        scroll_page(page, times=10)
        products = extract_douyin_products(page, limit=30)
        return store.insert_many(products)
    finally:
        browser.close()
        p.stop()


def run_scheduler(keywords: list[str], interval_seconds: int = 600, headless: bool = True) -> None:
    while True:
        for kw in keywords:
            try:
                saved = collect_keyword(kw, headless=headless)
                print(f"[{kw}] saved {saved} records")
            except Exception as err:
                print(f"[{kw}] collector failed: {err}")
            time.sleep(random.randint(300, interval_seconds))


if __name__ == "__main__":
    # example: python collector.py
    run_scheduler(["蓝牙耳机", "收纳", "美妆", "家居"], interval_seconds=600, headless=True)
