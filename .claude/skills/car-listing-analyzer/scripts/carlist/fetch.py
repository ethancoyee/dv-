"""Load listing pages in headless Chromium, follow pagination, detect blocking.

This module deliberately does NOT try to defeat anti-bot systems (no stealth
plugins, no CAPTCHA solving, no spoofed fingerprints). If a site challenges
the browser, we stop and report it.
"""
from __future__ import annotations

import glob
import json
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import extract
from .models import Vehicle

# Strong signals: present only on challenge / block pages.
BLOCK_MARKERS = [
    (r"pardon our interruption", "PerimeterX/HUMAN bot check"),
    (r"press\s*&\s*hold", "PerimeterX/HUMAN bot check"),
    (r"px-captcha", "PerimeterX/HUMAN bot check"),
    (r"just a moment\.\.\.|checking your browser|cf-chl-|challenge-platform", "Cloudflare challenge"),
    (r"attention required!? \| cloudflare", "Cloudflare block"),
    (r"request unsuccessful\. incapsula|_incapsula_resource|incapsula incident", "Imperva/Incapsula block"),
    (r"captcha-delivery\.com|datadome", "DataDome bot check"),
    (r"access denied.{0,200}reference\s*#", "Akamai block"),
    (r"you don't have permission to access", "Akamai block"),
    (r"verify (?:that )?you are (?:a )?human|are you a robot|unusual traffic from your", "bot check"),
    (r"automated (?:access|queries|requests)", "bot check"),
]
# Weak signals: only count as a block if the page also yielded zero listings.
WEAK_MARKERS = [r"captcha", r"access denied", r"forbidden", r"blocked"]

NEXT_SELECTORS = [
    "a[rel='next']",
    "link[rel='next']",
    "[aria-label='Next page']", "[aria-label='Next Page']", "[aria-label='next page']",
    "[aria-label='Next']", "[aria-label='next']",
    "[data-testid*='next' i]", "[data-cg-ft*='next' i]",
    "a.next", "li.next > a", "button.next", ".pagination-next a", ".pagination__next",
]
NEXT_TEXT_RE = re.compile(r"^\s*(next|next page|›|»|>|next ›|next »|next >)\s*$", re.I)
LOAD_MORE_RE = re.compile(r"^\s*(load|show|see|view)\s+more(\s+(results|vehicles|cars|listings))?\s*$", re.I)
PAGE_PARAMS = ["page", "pageNumber", "pageNum", "p", "pg", "pn", "currentPage"]

# Finds listing "cards": the largest element containing exactly one
# "YEAR MAKE" headline and a dollar amount.
CARDS_JS = r"""
() => {
  const priceRe = /\$\s?\d{1,3}(,\d{3})+|\$\s?\d{4,6}/;
  const titleRe = /\b(19[89]\d|20[0-4]\d)\s+[A-Z][A-Za-z-]+/;
  const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
  const hits = all.filter(e => {
    if (['SCRIPT','STYLE','NOSCRIPT','HEAD','BODY','HTML'].includes(e.tagName)) return false;
    const t = e.innerText || '';
    return t.length < 3000 && titleRe.test(t) && priceRe.test(t);
  });
  const minimal = hits.filter(e => !hits.some(o => o !== e && e.contains(o)));
  const cards = new Set();
  for (const m of minimal) {
    let el = m;
    while (el.parentElement && el.parentElement !== document.body) {
      const p = el.parentElement;
      const n = minimal.filter(o => p.contains(o)).length;
      if (n !== 1 || (p.innerText || '').length > 3000) break;
      el = p;
    }
    cards.add(el);
  }
  return Array.from(cards).map(el => {
    let a = el.tagName === 'A' ? el : el.querySelector('a[href]');
    return { text: el.innerText || '', href: a ? a.href : null };
  });
}
"""


@dataclass
class FetchResult:
    vehicles: list[Vehicle] = field(default_factory=list)
    pages_visited: int = 0
    status: str = "ok"            # ok | partial | blocked | unreachable | no_listings | error
    message: str = ""
    block_vendor: str | None = None
    log: list[str] = field(default_factory=list)


def detect_block(status: int | None, title: str, html: str, n_listings: int) -> tuple[bool, str | None]:
    hay = (title + "\n" + html[:200_000]).lower()
    for pattern, vendor in BLOCK_MARKERS:
        if re.search(pattern, hay, re.I | re.S):
            # A real inventory page that merely mentions one of these words
            # (e.g. a footer) still yields listings; trust the listings.
            if n_listings == 0:
                return True, vendor
    if status in (401, 403, 429) and n_listings == 0:
        return True, f"HTTP {status}"
    if n_listings == 0 and any(re.search(p, title.lower()) for p in WEAK_MARKERS):
        return True, "access-denied page"
    return False, None


def _launch(p, headless: bool):
    try:
        return p.chromium.launch(headless=headless)
    except Exception as first:  # bundled browser missing / version mismatch
        candidates = [os.environ.get("CHROMIUM_PATH"), "/opt/pw-browsers/chromium"]
        candidates += sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), reverse=True)
        candidates += sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"), reverse=True)
        candidates += ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    return p.chromium.launch(headless=headless, executable_path=path)
                except Exception:
                    continue
        raise RuntimeError("Could not start Chromium. Run `python -m playwright install chromium` "
                           f"or set CHROMIUM_PATH. Original error: {str(first).splitlines()[0]}")


def extract_page(html: str, ld_blocks: list[str], json_payloads: list, cards: list[dict], url: str) -> list[Vehicle]:
    groups = [extract.from_jsonld_blocks(ld_blocks, url)]
    for payload in json_payloads:
        groups.append(extract.from_json(payload, "json", url))
    groups.append([v for c in cards if (v := extract.from_card(c.get("text", ""), c.get("href")))])
    return extract.merge_all(groups)


def _embedded_json(page) -> list:
    """Inline JSON state blobs (Next.js, Redux preloads, etc.)."""
    raw = page.evaluate(r"""
      () => {
        const out = [];
        for (const s of document.querySelectorAll('script')) {
          const t = s.type || '';
          if (t === 'application/ld+json') continue;
          const txt = s.textContent || '';
          if (t === 'application/json' || s.id === '__NEXT_DATA__') { out.push(txt); continue; }
          const m = txt.match(/^\s*(?:window\.)?[\w$.]+\s*=\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*;?\s*$/);
          if (m && txt.length < 5e6) out.push(m[1]);
        }
        return out;
      }""")
    out = []
    for txt in raw:
        try:
            out.append(json.loads(txt))
        except (ValueError, TypeError):
            pass
    return out


def _settle(page, timeout_ms: int):
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15000))
    except Exception:
        pass
    # Scroll to trigger lazy-loaded cards.
    last = 0
    for _ in range(8):
        try:
            h = page.evaluate("() => { window.scrollTo(0, document.body.scrollHeight); return document.body.scrollHeight; }")
        except Exception:
            break
        page.wait_for_timeout(600)
        if h == last:
            break
        last = h
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass


def _find_next(page):
    """Return ('href', url) | ('click', locator) | (None, None)."""
    for sel in NEXT_SELECTORS:
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 5)):
                el = loc.nth(i)
                if _disabled(el):
                    continue
                href = el.get_attribute("href")
                if href and not href.startswith(("javascript", "#")):
                    return "href", el.evaluate("e => e.href || new URL(e.getAttribute('href'), location.href).href")
                if sel != "link[rel='next']" and el.is_visible():
                    return "click", el
        except Exception:
            continue
    for role in ("link", "button"):
        try:
            for rx in (NEXT_TEXT_RE, LOAD_MORE_RE):
                loc = page.get_by_role(role, name=rx)
                for i in range(min(loc.count(), 5)):
                    el = loc.nth(i)
                    if el.is_visible() and not _disabled(el):
                        href = el.get_attribute("href")
                        if href and not href.startswith(("javascript", "#")):
                            return "href", el.evaluate("e => e.href")
                        return "click", el
        except Exception:
            continue
    return None, None


def _disabled(el) -> bool:
    try:
        return bool(el.evaluate(
            "e => e.disabled || e.getAttribute('aria-disabled') === 'true' || "
            "/(^|\\s)(disabled|is-disabled)(\\s|$)/.test(e.className || '') || "
            "!!(e.parentElement && /(^|\\s)disabled(\\s|$)/.test(e.parentElement.className || ''))"))
    except Exception:
        return False


def _bump_page_param(url: str) -> str | None:
    parts = urlparse(url)
    q = parse_qsl(parts.query, keep_blank_values=True)
    for i, (k, v) in enumerate(q):
        if k in PAGE_PARAMS and v.isdigit():
            q[i] = (k, str(int(v) + 1))
            return urlunparse(parts._replace(query=urlencode(q)))
    return None


def fetch(url: str, max_pages: int = 20, timeout_ms: int = 45000, delay_s: float = 1.5,
          headless: bool = True) -> FetchResult:
    res = FetchResult()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        res.status, res.message = "error", "Playwright is not installed: pip install playwright && python -m playwright install chromium"
        return res

    collected: dict[str, Vehicle] = {}
    try:
        with sync_playwright() as p:
            browser = _launch(p, headless)
            ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
            page = ctx.new_page()
            payloads: list = []

            def on_response(resp):
                try:
                    ctype = resp.headers.get("content-type", "")
                    if "json" in ctype and resp.request.resource_type in ("xhr", "fetch"):
                        payloads.append(resp.json())
                except Exception:
                    pass
            page.on("response", on_response)

            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as e:
                msg = str(e).splitlines()[0]
                res.status = "unreachable"
                res.message = (f"Could not load the page ({msg}). The site may be down, the URL wrong, or this "
                               "environment's network does not allow outbound access to that host.")
                browser.close()
                return res
            http_status = resp.status if resp else None

            seen_urls = {page.url}
            for page_no in range(1, max_pages + 1):
                _settle(page, timeout_ms)
                html = page.content()
                title = page.title() or ""
                ld = page.eval_on_selector_all("script[type='application/ld+json']", "els => els.map(e => e.textContent)")
                try:
                    cards = page.evaluate(CARDS_JS)
                except Exception:
                    cards = []
                found = extract_page(html, ld, payloads + _embedded_json(page), cards, page.url)
                payloads.clear()

                blocked, vendor = detect_block(http_status, title, html, len(found))
                res.pages_visited = page_no
                if blocked:
                    res.block_vendor = vendor
                    res.status = "blocked" if not collected else "partial"
                    res.message = (f"The site blocked automated access on page {page_no} ({vendor}; page title: "
                                   f"'{title[:80]}'). This tool does not bypass bot protection.")
                    break

                new = 0
                for v in found:
                    k = v.key()
                    if k in collected:
                        collected[k].merge(v)
                    else:
                        collected[k] = v
                        new += 1
                res.log.append(f"page {page_no}: {len(found)} listings parsed, {new} new ({page.url})")
                if page_no > 1 and new == 0:
                    res.log.append("no new listings on this page; stopping pagination")
                    break
                if page_no == max_pages:
                    res.log.append(f"reached --max-pages={max_pages}; there may be more listings")
                    break

                kind, target = _find_next(page)
                if kind is None:
                    bumped = _bump_page_param(page.url)
                    if bumped and bumped not in seen_urls:
                        kind, target = "href", bumped
                if kind is None:
                    res.log.append("no next-page control found; done")
                    break
                time.sleep(delay_s)
                try:
                    if kind == "href":
                        if target in seen_urls:
                            res.log.append("next link points to a page already visited; done")
                            break
                        resp = page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                        http_status = resp.status if resp else None
                    else:
                        target.scroll_into_view_if_needed(timeout=5000)
                        target.click(timeout=10000)
                        http_status = None
                        page.wait_for_timeout(1500)
                    seen_urls.add(page.url)
                except Exception as e:
                    res.log.append(f"could not open next page: {str(e).splitlines()[0]}")
                    res.status = "partial"
                    res.message = "Stopped early: navigation to the next page failed."
                    break
            browser.close()
    except Exception as e:
        res.status = "error" if not collected else "partial"
        res.message = f"Browser error: {str(e).splitlines()[0] if str(e) else type(e).__name__}"

    res.vehicles = list(collected.values())
    if res.status == "ok" and not res.vehicles:
        res.status = "no_listings"
        res.message = ("The page loaded but no vehicle listings could be recognized. It may need a different "
                       "URL (a search-results page, not a home page), or the layout is unusual.")
    return res


def parse_saved_html(paths: list[str]) -> FetchResult:
    """Offline mode: analyze pages the user saved from their own browser."""
    res = FetchResult()
    collected: dict[str, Vehicle] = {}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = _launch(p, True)
            page = browser.new_page()
            # Saved pages must not phone home; we only want the DOM as saved.
            page.route("**/*", lambda r: r.abort() if not r.request.url.startswith("file:") else r.continue_())
            for path in paths:
                try:
                    page.goto("file://" + os.path.abspath(path), wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1000)  # let any inline scripts render
                    ld = page.eval_on_selector_all("script[type='application/ld+json']", "els => els.map(e => e.textContent)")
                    found = extract_page(page.content(), ld, _embedded_json(page), page.evaluate(CARDS_JS), page.url)
                except Exception as e:
                    res.log.append(f"{path}: could not parse ({str(e).splitlines()[0]})")
                    continue
                res.pages_visited += 1
                for v in found:
                    collected.setdefault(v.key(), v).merge(v)
                res.log.append(f"{path}: {len(found)} listings parsed")
            browser.close()
    except Exception as e:
        res.status, res.message = "error", f"Browser error: {str(e).splitlines()[0]}"
    res.vehicles = list(collected.values())
    if res.status == "ok" and not res.vehicles:
        res.status, res.message = "no_listings", "No vehicle listings recognized in the saved file(s)."
    return res
