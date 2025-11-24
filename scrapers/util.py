import random
import time
import requests
from typing import Optional, Dict
import re

# Simple UA rotation (extend this list in production)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/117.0"
]

DEFAULT_TIMEOUT = 12
DEFAULT_RETRIES = 3

def make_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

def smart_get(url: str, proxies: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES):
    """
    Do GET with UA rotation and simple retry/backoff. Raises requests.RequestException on final failure.
    """
    backoff = 1.0
    for i in range(retries):
        try:
            resp = requests.get(url, headers=make_headers(), timeout=timeout, proxies=proxies)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if i == retries - 1:
                raise
            time.sleep(backoff + random.random() * 0.5)
            backoff *= 2
    raise RuntimeError("unreachable")

def is_blocked_html(html: str) -> bool:
    """
    Heuristics to detect bot-block pages (very small HTML or 'robot' checks, captcha).
    """
    if not html or len(html) < 2000:
        return True
    lower = html.lower()
    checks = [
        "enter the characters you see below",
        "are you a human",
        "robot check",
        "detected unusual traffic",
        "justify your browser",
        "to discuss automated access to amazon data"
    ]
    return any(ch in lower for ch in checks)

def parse_price(text: Optional[str]) -> Optional[float]:
    """
    Convert price-like string to float safely.
    If numeric result is unrealistic (<20 or >5000), return None.
    Examples:
    "$1,949.00", "1,949.00", "US$ 2999", "$2,999 – $3,499"
    """
    if not text:
        return None

    # Keep only digits, dot, comma
    s = re.sub(r"[^\d\.,]", "", text)

    # Case: "1,299.00" → OK
    if "," in s and "." in s:
        s = s.replace(",", "")

    # Case: "1.299,00" (EU format)
    elif s.count(".") > 1 and "," in s:
        s = s.replace(".", "").replace(",", ".")

    # Case: only commas → thousands separator
    elif "," in s and "." not in s:
        s = s.replace(",", "")

    s = s.strip()

    try:
        val = float(s)
    except:
        return None

    # --- Sanity check (GPU range) ---
    if val < 20 or val > 5000:
        print(f"[!] Price out of range ({val}) → ignoring")
        return None

    return val

def extract_asin_from_url(url: str) -> Optional[str]:
    """
    Common patterns: /dp/ASIN, /gp/product/ASIN
    """
    if not url:
        return None
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    m = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    # fallback: look for /product/...
    m = re.search(r"/product/([A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    return None