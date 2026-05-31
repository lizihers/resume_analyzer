"""URL content fetching with browser-like headers."""
import requests
import trafilatura


def read_url(url: str) -> str:
    """Fetch and extract readable text from a URL."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        return f"[错误] 网络请求失败: {type(e).__name__} — {e}"

    if not resp.ok:
        return f"[错误] 服务器返回 HTTP {resp.status_code}\nURL: {url}"

    html = resp.text
    if not html:
        return "[错误] 网页无内容"

    # Try trafilatura first (best extraction quality)
    text = trafilatura.extract(html, include_links=False, include_images=False,
                               include_tables=False, output_format="markdown")
    if text and len(text.strip()) > 100:
        return text.strip()

    # Fallback to BeautifulSoup
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    body = soup.find("body")
    text = body.get_text(separator="\n") if body else soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines[:200]) if lines else "[错误] 无法提取网页内容"
