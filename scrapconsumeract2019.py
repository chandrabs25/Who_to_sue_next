import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import json
import time

# --- CONFIGURATION ---
BASE_URL = "https://www.indiacode.nic.in"
# The Main Page where all chapters are listed
MAIN_ACT_URL = "https://www.indiacode.nic.in/handle/123456789/15256"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_chapter_urls_from_main_page():
    """
    Parses the main page to find hidden Chapter IDs and constructs their URLs.
    Mimics the JavaScript logic found in the website source code.
    """
    print(f"🕵️‍♂️ Scanning Main Page for Chapters...")
    response = requests.get(MAIN_ACT_URL, headers=HEADERS)

    chapter_list = []

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # We found that chapters use the class "headingtwo"
        chapter_links = soup.find_all('a', class_='headingtwo')

        print(f"✅ Found {len(chapter_links)} Chapters.")

        for link in chapter_links:
            title = link.get_text(strip=True)
            element_id = link.get('id')  # This ID holds the secret numbers

            if element_id:
                # The JS logic splits the ID by '#'
                # Format: act_id # h1id # h2id # orgID
                parts = element_id.split('#')

                if len(parts) >= 4:
                    act_id = parts[0]
                    h1id = parts[1]
                    h2id = parts[2]
                    org_id = parts[3]

                    # Construct the URL manually (Reverse Engineering the JS)
                    # Note: The JS uses h1id for both h3id and h4id
                    chapter_url = (
                        f"{BASE_URL}/ChapterIndexWiseSection?"
                        f"abv=CEN&statehandle=123456789/1362"
                        f"&actid={act_id}&h1id={h1id}&h2id={h2id}"
                        f"&h3id={h1id}&h4id={h1id}&orgactid={org_id}"
                        f"&headingno=headingtwo"
                    )

                    chapter_list.append({
                        "title": title,
                        "url": chapter_url
                    })
                    print(f"   -> Discovered: {title}")

    return chapter_list


def fetch_section_text(full_url):
    """Hits the hidden API to get the text for a specific section."""
    try:
        parsed_url = urlparse(full_url)
        params = parse_qs(parsed_url.query)

        act_id = params.get('actid', [None])[0]
        section_id = params.get('sectionId', [None])[0]

        if not act_id or not section_id:
            return None

        api_url = f"{BASE_URL}/SectionPageContent?actid={act_id}&sectionID={section_id}"
        response = requests.get(api_url, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()
            clean_text = BeautifulSoup(data['content'], 'html.parser').get_text(separator="\n", strip=True)
            return clean_text
    except:
        return None
    return None


def scrape_entire_act():
    # 1. Get all Chapter URLs first
    chapters = get_chapter_urls_from_main_page()

    full_act_data = []

    # 2. Loop through each Chapter
    for i, chapter in enumerate(chapters):
        print(f"\n📚 Processing Chapter {i + 1}/{len(chapters)}: {chapter['title']}")

        response = requests.get(chapter['url'], headers=HEADERS)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a')

            # Find valid section links
            section_links = [l for l in links if l.get('href') and 'show-data' in l.get('href')]

            print(f"   Found {len(section_links)} sections.")

            chapter_sections = []

            # 3. Loop through each Section in this Chapter
            for link in section_links:
                sec_title = link.get_text(strip=True)
                full_link = BASE_URL + link['href']

                print(f"      Downloading: {sec_title[:40]}...")

                content = fetch_section_text(full_link)

                if content:
                    chapter_sections.append({
                        "title": sec_title,
                        "content": content,
                        "url": full_link
                    })

                # Polite pause
                time.sleep(0.5)

            # Add this chapter to our main list
            full_act_data.append({
                "chapter_name": chapter['title'],
                "sections": chapter_sections
            })

    # 4. Save EVERYTHING to JSON
    filename = "consumer_protection_act_2019.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(full_act_data, f, indent=4, ensure_ascii=False)

    print(f"\n✅ SUCCESS! Entire Act saved to {filename}")


if __name__ == '__main__':
    scrape_entire_act()