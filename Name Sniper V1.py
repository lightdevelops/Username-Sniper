#!/usr/bin/env python3
"""Large-dictionary Roblox + GitHub username finder.

Downloads a large English word list on first use, caches it locally, and
randomly samples words. Also supports random 3–5 letter usernames.

Checks are indicators only, not guarantees of registration availability.
The script makes sequential requests with pauses and stops on rate limits.
"""

import json
import random
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WORDLIST_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
WORDLIST_FILE = Path("words_alpha.txt")
ROBLOX_API = "https://auth.roblox.com/v1/usernames/validate"
GITHUB_API = "https://api.github.com/users/{}"
USER_AGENT = "PersonalUsernameResearch/1.0"
REQUEST_DELAY_SECONDS = 5
MAX_CANDIDATES_PER_RUN = 30


def http_get(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def load_wordlist():
    if WORDLIST_FILE.exists() and WORDLIST_FILE.stat().st_size > 100_000:
        print(f"Using cached dictionary: {WORDLIST_FILE}")
        raw = WORDLIST_FILE.read_text(encoding="utf-8", errors="ignore")
    else:
        print("Downloading the large English word list (first run only)...")
        try:
            raw = http_get(WORDLIST_URL).decode("utf-8", errors="ignore")
            WORDLIST_FILE.write_text(raw, encoding="utf-8")
            print(f"Saved dictionary locally as {WORDLIST_FILE}")
        except Exception as exc:
            raise RuntimeError(
                "Could not download the dictionary. Check your internet connection."
            ) from exc

    return sorted({
        line.strip().lower()
        for line in raw.splitlines()
        if line.strip().isalpha()
    })


def check_roblox(username):
    query = urllib.parse.urlencode({
        "request.username": username,
        "request.birthday": "2000-01-01T00:00:00.000Z",
        "request.context": "Signup",
    })
    try:
        data = json.loads(http_get(f"{ROBLOX_API}?{query}").decode("utf-8"))
        code = data.get("code")
        if code == 0:
            return "PASSES VALIDATION (signup must confirm)"
        if code == 1:
            return "TAKEN"
        return f"NOT CONFIRMED (Roblox code {code})"
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            return "RATE LIMITED"
        return f"NOT CONFIRMED (HTTP {exc.code})"
    except Exception as exc:
        return f"NOT CONFIRMED ({type(exc).__name__})"


def check_github(username):
    url = GITHUB_API.format(urllib.parse.quote(username, safe=""))
    try:
        http_get(url)
        return "TAKEN (public profile exists)"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "NO PUBLIC PROFILE (registration not confirmed)"
        if exc.code == 429:
            return "RATE LIMITED"
        return f"NOT CONFIRMED (HTTP {exc.code})"
    except Exception as exc:
        return f"NOT CONFIRMED ({type(exc).__name__})"


def ask_int(prompt, low, high):
    while True:
        try:
            value = int(input(prompt))
            if low <= value <= high:
                return value
        except ValueError:
            pass
        print(f"Enter a whole number from {low} to {high}.")


def main():
    print("=" * 62)
    print("       LARGE-DICTIONARY ROBLOX + GITHUB USERNAME FINDER")
    print("=" * 62)
    print("1. Dictionary words (large English word list)")
    print("2. Random letters (3–5 characters)")
    print("3. Both")
    mode = input("Choose 1, 2, or 3: ").strip()
    if mode not in {"1", "2", "3"}:
        print("Invalid selection.")
        return

    words = []
    if mode in {"1", "3"}:
        try:
            words = load_wordlist()
        except RuntimeError as exc:
            print(exc)
            return
        print(f"Loaded {len(words):,} unique alphabetic words.")

    min_len, max_len = 5, 20
    if mode in {"1", "3"}:
        min_len = ask_int("Minimum dictionary-word length (5–20): ", 5, 20)
        max_len = ask_int(f"Maximum word length ({min_len}–30): ", min_len, 30)

    count = ask_int(f"How many candidates this run? (1–{MAX_CANDIDATES_PER_RUN}): ",
                    1, MAX_CANDIDATES_PER_RUN)

    candidates = set()
    if mode in {"1", "3"}:
        matching = [word for word in words if min_len <= len(word) <= max_len]
        random.shuffle(matching)
        candidates.update(matching[:count])

    if mode in {"2", "3"}:
        random_names = set()
        alphabet = string.ascii_lowercase
        while len(random_names) < count:
            length = random.randint(3, 5)
            random_names.add("".join(random.choices(alphabet, k=length)))
        candidates.update(random_names)

    candidates = list(candidates)
    random.shuffle(candidates)
    candidates = candidates[:count]
    if not candidates:
        print("No candidates matched those settings.")
        return

    print(f"\nChecking {len(candidates)} candidates sequentially.")
    print(f"Pausing {REQUEST_DELAY_SECONDS} seconds between requests.")
    print("Press Ctrl+C to stop; collected results will be saved.\n")

    results = []
    try:
        for index, username in enumerate(candidates, 1):
            time.sleep(REQUEST_DELAY_SECONDS)
            roblox = check_roblox(username)
            time.sleep(REQUEST_DELAY_SECONDS)
            github = check_github(username)

            results.append({"username": username, "roblox": roblox, "github": github})
            print(f"[{index}/{len(candidates)}] {username}")
            print(f"  Roblox: {roblox}")
            print(f"  GitHub: {github}\n")

            if "RATE LIMITED" in roblox or "RATE LIMITED" in github:
                print("A platform rate-limited the requests. Stopping this run.")
                break
    except KeyboardInterrupt:
        print("\nStopped. Saving results collected so far...")

    # These files contain promising leads, not guaranteed available names.
    roblox_leads = [
        x["username"] for x in results
        if x["roblox"].startswith("PASSES VALIDATION")
    ]
    github_leads = [
        x["username"] for x in results
        if x["github"].startswith("NO PUBLIC PROFILE")
    ]

    Path("roblox_candidates.txt").write_text("\n".join(roblox_leads), encoding="utf-8")
    Path("github_candidates.txt").write_text("\n".join(github_leads), encoding="utf-8")

    with open("all_username_results.txt", "w", encoding="utf-8") as out:
        out.write("USERNAME SCAN RESULTS — manually confirm before signup\n\n")
        for item in results:
            out.write(f"{item['username']}\n")
            out.write(f"  Roblox: {item['roblox']}\n")
            out.write(f"  GitHub: {item['github']}\n\n")

    print("Saved:")
    print(f"  roblox_candidates.txt ({len(roblox_leads)} leads)")
    print(f"  github_candidates.txt ({len(github_leads)} leads)")
    print("  all_username_results.txt")


if __name__ == "__main__":
    main()
