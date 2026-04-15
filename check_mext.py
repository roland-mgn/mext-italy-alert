import json
import hashlib
import requests
from bs4 import BeautifulSoup
from pathlib import Path

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
    session.headers.update(HEADERS)
    r = session.get(URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # --- sezione studio ---
    # Cerca tutti i tag che contengono link a URL con "studio" nel percorso
    studio_items = []
    for a in soup.find_all("a", href=True):
        if "studio" in a["href"].lower():
            # Risali al contenitore più vicino (li, div, p, td)
            parent = a.find_parent(["li", "div", "p", "td", "tr"])
            item_text = normalize(parent.get_text(" ", strip=True)) if parent else normalize(a.get_text(" ", strip=True))
            if item_text and item_text not in studio_items:
                studio_items.append(item_text)

    studio_text = "\n".join(studio_items) if studio_items else ""
    studio_hash = make_hash(studio_text)

    # --- hash intera pagina ---
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    full_text = normalize(soup.get_text("\n", strip=True))
    full_hash = make_hash(full_text)

    return studio_text, studio_hash, full_hash

def main():
    state = load_state()
    studio_text, studio_hash, full_hash = extract_data()

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
