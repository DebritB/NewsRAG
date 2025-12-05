import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean_article_text(text: str) -> str:
    """Clean article text: remove excessive whitespace and trailing disclaimers/footers."""
    txt = re.sub(r"\r\n|\r", "\n", text)
    txt = re.sub(r"\n{2,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    # Remove common 'Read more' or social tags
    txt = re.sub(r"\s*Read more.*$", "", txt, flags=re.I | re.M)
    txt = re.sub(r"\s*RELATED:.*$", "", txt, flags=re.I | re.M)
    txt = txt.strip()
    return txt


def is_placeholder_text(text: str) -> bool:
    """Detect placeholder text commonly used for paywalled or unavailable content.
    Returns True if the text seems like a site message rather than article content.
    """
    if not text or len(text.strip()) == 0:
        return True
    t = text.strip().lower()
    placeholders = [
        r"we['’]?re sorry",
        r"this feature is currently unavailable",
        r"please try again later",
        r"please sign in",
        r"subscribe to continue",
        r"subscription required",
        r"sign in to read",
        r"please log in",
        r"feature is temporarily unavailable",
        r"you must be a subscriber",
    ]
    for p in placeholders:
        if re.search(p, t):
            return True
    # Very short content is likely not a full article
    if len(t) < 120:
        return True
    return False


def extract_full_content_from_url(url: str, timeout: int = 10) -> tuple[str, str]:
    """Fetch and parse the full article content from the URL.

    Returns: (cleaned_text, strategy)
    strategy is a string like 'selector:article' or 'heuristic:max-paragraphs' or 'fallback:body-paragraphs' or 'none' or 'error'
    """
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        for tag in soup(['script', 'style', 'noscript', 'iframe', 'form', 'nav', 'aside', 'header', 'footer']):
            tag.decompose()

        selectors = [
            "div[data-testid=article-body]",
            "article",
            "div[itemprop=articleBody]",
            "div[class*='article__body']",
            "div[class*='article-body']",
            "div[class*='content-body']",
            "div[class*='main-content']",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                paragraphs = el.find_all('p')
                text = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                if len(text) > 100:
                    return clean_article_text(text), f"selector:{sel}"

        candidates = []
        for div in soup.find_all(['div', 'article', 'main']):
            ps = div.find_all('p')
            if len(ps) >= 2:
                text = "\n".join(p.get_text().strip() for p in ps if p.get_text().strip())
                candidates.append((len(ps), len(text), text))
        if candidates:
            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best_text = candidates[0][2]
            if len(best_text) > 100:
                return clean_article_text(best_text), "heuristic:max-paragraphs"

        body = soup.body
        if body:
            paragraphs = body.find_all('p')
            text = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
            if len(text) > 100:
                return clean_article_text(text), "fallback:body-paragraphs"

        return "", "none"
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return "", "error"
    except Exception as e:
        logger.error(f"Error parsing HTML for URL {url}: {e}")
        return "", "error"


def sanitize_text(text: str) -> str:
    """Remove HTML tags, collapse whitespace and strip emojis and control chars.

    Returns plain text suitable for JSON or downstream NLP pipelines.
    """
    if not text:
        return text
    try:
        # If the text contains HTML tags, use BeautifulSoup to strip them.
        soup = BeautifulSoup(text, 'html.parser')
        txt = soup.get_text(separator=' ', strip=True)
    except Exception:
        txt = text
    # Remove control chars
    txt = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', txt)
    # Collapse multiple whitespace
    txt = re.sub(r'\s{2,}', ' ', txt).strip()
    # Remove common emojis and pictographs
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002700-\U000027BF"  # Dingbats
        u"\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "]+", flags=re.UNICODE)
    txt = emoji_pattern.sub('', txt)
    # Remove common UI strings, share prompts, and subscription prompts/advertisements
    ui_patterns = [
        r'(?im)^\s*read (more|this|more:).*$',
        r'(?im)^\s*continue reading.*$',
        r'(?im)^\s*watch( the video)?( above)?[:\s].*$',
        r'(?im)^\s*share this.*$',
        r'(?im)^\s*login or sign(up|in).*$',
        r'(?im)^\s*please sign (in|up).*$',
        r'(?im)^\s*subscribe to (continue|read|our).*$',
        r'(?im)^\s*subscription required.*$',
        r'(?im)^\s*advertis(e|ement).*$',
        r'(?im)^\s*download (today|the app).*$',
        r'(?im)^\s*click here.*$',
        r'(?im)^\s*related:.*$',
        r'(?im)^\s*read next:.*$',
        r'(?im)^\s*see also:.*$',
        r'(?im)^\s*know the news with.*$',
        r'(?im)^\s*watch the video above.*$',
        r'(?im)^\s*watch:.*$',
        r'(?im)^\s*topic:.*$',
        r'(?im)^\s*source:.*$',
        r'(?im)^\s*credit:.*$',
        r'(?im)^\s*image:.*$',
        r'(?im)^\s*signup to continue.*$',
        r'(?im)^\s*login to continue.*$',
    ]
    for p in ui_patterns:
        txt = re.sub(p, '', txt)
    # Remove inline 'Topic:', 'Credit:', 'Source:' markers, often concatenated without newlines
    txt = re.sub(r'(?i)topic:\s*[^\n\.|,\;\-]*', '', txt)
    txt = re.sub(r'(?i)credit:\s*[^\n\.|,\;\-]*', '', txt)
    txt = re.sub(r'(?i)source:\s*[^\n\.|,\;\-]*', '', txt)
    # Remove common short disclaimer or site-specific replicated lines
    txt = re.sub(r'(?im)^\s*why this matters:.*$', '', txt)
    txt = re.sub(r'(?im)^\s*read next:.*$', '', txt)
    # Also remove lines containing only punctuation or short social prompts
    txt = re.sub(r'(?m)^\s*[-_\*\s]+\s*$', '', txt)
    txt = re.sub(r'(?m)^\s*(share|tweet|like|follow).*$', '', txt, flags=re.I)
    # Remove any excessive leading/trailing whitespace
    txt = txt.strip()
    return txt


def sanitize_text_alnum_only(text: str) -> str:
    """Sanitize text strictly: only ASCII alphanumeric chars and whitespace kept.

    Intended for dev or testing scenarios while production may prefer a more permissive sanitizer.
    """
    if not text:
        return text
    # Reuse the regular sanitizer to remove UI/patterns first
    txt = sanitize_text(text)
    txt = txt.replace("'", "").replace('"', '')
    txt = re.sub(r'[^A-Za-z0-9\s]', '', txt)
    txt = re.sub(r'\s{2,}', ' ', txt).strip()
    return txt
