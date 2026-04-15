import json
import hashlib
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
from pathlib import Path

# Sopprimi warning SSL dovuto a verify=False con ScraperAPI
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

URL = "https://www.it.emb-japan.go.jp/itpr_it/index.html"
STATE_FILE = Path("state.json")
OUTPUT_FILE = Path("email_body.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
}

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}

def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def normalize(text):
    return " ".join(text.split())

def make_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def extract_data():
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)

    api_key = os.getenv("SCRAPER_API_KEY")
    proxies = None
    if api_key:
        proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
        proxies = {"http": proxy_url, "https": proxy_url}

    try:
        r = session.get(URL, proxies=proxies, timeout=60, verify=False)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("warning=403")
            return None, None, None
        raise

    soup = BeautifulSoup(r.text, "html.parser")

    # Sezione studio: tutti i link che puntano a URL con "studio" nel percorso
    studio_items = []
    for a in soup.find_all("a", href=True):
        if "studio" in a["href"].lower():
            parent = a.find_parent(["li", "div", "p", "td", "tr"])
            item_text = normalize(
                parent.get_text(" ", strip=True) if parent
                else a.get_text(" ", strip=True)
            )
            if item_text and item_text not in studio_items:
                studio_items.append(item_text)

    studio_text = "\n".join(studio_items) if studio_items else ""
    studio_hash = make_hash(studio_text)

    # Hash intera pagina
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    full_text = normalize(soup.get_text("\n", strip=True))
    full_hash = make_hash(full_text)

    return studio_text, studio_hash, full_hash

def main():
    state = load_state()
    studio_text, studio_hash, full_hash = extract_data()

    # Se la richiesta è stata bloccata, salta senza toccare lo stato
    if studio_hash is None:
        print("changed=false")
        return

    last_studio_hash = state.get("last_studio_hash")
    last_full_hash = state.get("last_full_hash")

    studio_changed = studio_hash != last_studio_hash
    page_changed = full_hash != last_full_hash
    changed = studio_changed or page_changed

    state["last_studio_hash"] = studio_hash
    state["last_full_hash"] = full_hash
    save_state(state)

    if changed:
        lines = []
        lines.append("Aggiornamento rilevato sul sito dell'Ambasciata del Giappone in Italia.")
        lines.append(f"Link: {URL}")
        lines.append("")

        if studio_changed:
            lines.append("✅ La sezione STUDIO è cambiata. Contenuto attuale:")
            lines.append("")
            lines.append(studio_text if studio_text else "(nessun link studio trovato)")
        else:
            lines.append("ℹ️ La sezione STUDIO non è cambiata.")

        if page_changed:
            lines.append("")
            lines.append("⚠️ È cambiata anche un'altra parte della pagina (hash diverso).")

        OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
        print("changed=true")
    else:
        print("changed=false")

if __name__ == "__main__":
    main()
