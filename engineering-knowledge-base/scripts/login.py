from pathlib import Path
import argparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AUTH_DIR = ROOT / ".auth"
AUTH_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Example: substack")
    parser.add_argument("--url", required=True, help="Login URL")
    args = parser.parse_args()
    state_file = AUTH_DIR / f"{args.name}.json"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        print("Complete login in the opened browser, then press ENTER here.")
        input()
        context.storage_state(path=str(state_file))
        browser.close()
        print(f"Saved browser state to {state_file}")


if __name__ == "__main__":
    main()
