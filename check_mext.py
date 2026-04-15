import json
import hashlib
import requests
from bs4 import BeautifulSoup
from pathlib import Path

URL = "https://www.it.emb-japan.go.jp/itpr_it/studio_UndergraduateStudents.html"
STATE_FILE = Path("state.json")
OUTPUT_FILE = Path("email_body.txt")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}

def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def normalize_text(text):
    return " ".join(text.split())

def extract_page_data():
    r = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    title = None

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    elif soup.title and soup.title.text.strip():
        title = soup.title.text.strip()
    else:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else "Nuovo aggiornamento rilevato"

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    main_text = normalize_text(soup.get_text("\n", strip=True))
    content_hash = hashlib.sha256(main_text.encode("utf-8")).hexdigest()

    return title, content_hash

def main():
    state = load_state()

    current_title, current_hash = extract_page_data()
    last_title = state.get("last_title")
    last_hash = state.get("last_hash")

    title_changed = current_title != last_title
    hash_changed = current_hash != last_hash
    changed = title_changed or hash_changed

    state["last_title"] = current_title
    state["last_hash"] = current_hash
    save_state(state)

    if changed:
        reasons = []
        if title_changed:
            reasons.append("titolo cambiato")
        if hash_changed:
            reasons.append("contenuto cambiato (hash diverso)")

        OUTPUT_FILE.write_text(
            "Nuovo aggiornamento sul sito dell'Ambasciata del Giappone in Italia.\n\n"
            f"Titolo attuale: {current_title}\n"
            f"Controlli che hanno rilevato il cambiamento: {', '.join(reasons)}\n"
            f"Link: {URL}\n",
            encoding="utf-8"
        )
        print("changed=true")
    else:
        print("changed=false")

if __name__ == "__main__":
    main()
