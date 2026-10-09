
import json
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gmiu.edu.in/gmiu/website/"
COURSES_URL = urljoin(BASE_URL, "admission/courses_offered.php")
MAX_EXTRA_PAGES = 30
DELAY = 0.4

IMPORTANT_PAGES = [
    BASE_URL,
    COURSES_URL,
    urljoin(BASE_URL, "admission/how-to-apply.php"),
    urljoin(BASE_URL, "common/contact_us.php"),
    urljoin(BASE_URL, "admission/why_gmiu.php"),
    urljoin(BASE_URL, "about/about_university.php"),
    urljoin(BASE_URL, "faculty/all_programs.php"),
    urljoin(BASE_URL, "admission/scholarships.php"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GMIUStudentProject/1.0)"
}

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".rar", ".mp3", ".mp4", ".css", ".js"
)

session = requests.Session()
session.headers.update(HEADERS)


def normalize_url(url):
    url, _ = urldefrag(url)
    parsed = urlparse(url)

    # Remove query strings to avoid crawling the same page repeatedly.
    return parsed._replace(query="").geturl().rstrip("/")


def valid_url(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    if parsed.netloc.lower() != urlparse(BASE_URL).netloc.lower():
        return False

    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return False

    return True


def fetch_soup(url):
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_courses(soup):
    """
    Extract course records from the Courses Offered page.
    First inspect individual HTML elements, then try page text.
    """
    courses = []
    seen = set()

    course_pattern = re.compile(
        r"^(.+?)\s+Duration\s*:\s*(\d+)\s*Years?"
        r"\s+Intake\s*:\s*(\d+)\s*$",
        re.IGNORECASE
    )

    def add_course(text):
        text = clean_text(text)
        match = course_pattern.match(text)

        if not match:
            return

        name = match.group(1).strip(" -:;,|")
        duration = match.group(2)
        intake = match.group(3)

        if len(name) < 3:
            return

        # Avoid accidentally treating a whole page section as a course.
        if len(name) > 110:
            return

        key = (name.casefold(), duration, intake)

        if key in seen:
            return

        seen.add(key)
        courses.append({
            "name": name,
            "duration": duration,
            "intake": intake
        })

    # Course information is often contained in links or card elements.
    for element in soup.find_all(
        ["a", "li", "tr", "td", "div", "p", "h3", "h4"]
    ):
        text = " ".join(element.stripped_strings)
        add_course(text)

    # Fallback for layouts where the course information is spread
    # across neighboring HTML elements.
    if not courses:
        page_text = clean_text(soup.get_text(" ", strip=True))

        for match in re.finditer(
            r"Duration\s*:\s*(\d+)\s*Years?\s+Intake\s*:\s*(\d+)",
            page_text,
            re.IGNORECASE
        ):
            start = max(0, match.start() - 130)
            prefix = page_text[start:match.start()]

            # Keep only the text after the last likely section boundary.
            prefix = re.split(
                r"(?i)(?:DIPLOMA|UNDER GRADUATION|"
                r"POST GRADUATION|PHARMACY|SCIENCE|COMMERCE)",
                prefix
            )[-1]

            name_match = re.search(
                r"([A-Za-z][A-Za-z0-9 &()./,\-]{2,100})\s*$",
                prefix
            )

            if name_match:
                add_course(
                    f"{name_match.group(1)} "
                    f"{match.group(0)}"
                )

    return courses


def get_page_links(soup, current_url):
    links = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        url = normalize_url(urljoin(current_url, href))

        if valid_url(url):
            links.append(url)

    return list(dict.fromkeys(links))


def scrape_page(url):
    print(f"Scraping: {url}")

    try:
        soup = fetch_soup(url)
    except requests.RequestException as error:
        print(f"  ERROR: {error}")
        return None, []

    links = get_page_links(soup, url)

    is_courses_page = (
        "courses_offered.php" in url.lower()
    )

    courses = extract_courses(soup) if is_courses_page else []

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title else "GMIU"
    )

    for element in soup([
        "script", "style", "nav", "footer", "header", "noscript"
    ]):
        element.decompose()

    content = clean_text(soup.get_text(" ", strip=True))

    page_data = {
        "url": url,
        "title": title,
        "content": content,
    }

    if is_courses_page:
        page_data["courses"] = courses
        print(f"  Course records extracted: {len(courses)}")

        if not courses:
            print(
                "  WARNING: No course records were detected. "
                "Inspect the course page HTML."
            )

    if len(content) < 30 and not courses:
        print("  Skipped: insufficient text.")
        return None, links

    print("  Page saved.")
    return page_data, links


def main():
    print("=" * 55)
    print("GMIU COLLEGE WEBSITE SCRAPER")
    print("=" * 55)

    important = list(dict.fromkeys(
        normalize_url(url) for url in IMPORTANT_PAGES
    ))

    queue = deque(important)
    queued = set(important)
    visited = set()
    pages = []
    extra_pages_count = 0

    while queue:
        url = queue.popleft()

        if url in visited:
            continue

        is_important = url in important

        if not is_important and extra_pages_count >= MAX_EXTRA_PAGES:
            continue

        visited.add(url)

        page_data, links = scrape_page(url)

        if page_data:
            pages.append(page_data)

        if not is_important:
            extra_pages_count += 1

        # Discover new pages only while room remains for extra pages.
        if is_important or extra_pages_count < MAX_EXTRA_PAGES:
            for link in links:
                if link not in visited and link not in queued:
                    queue.append(link)
                    queued.add(link)

        time.sleep(DELAY)

    with open("college_data.json", "w", encoding="utf-8") as file:
        json.dump(pages, file, indent=2, ensure_ascii=False)

    course_page = next(
        (
            page for page in pages
            if "courses_offered.php" in page["url"].lower()
        ),
        None
    )

    print("\n" + "=" * 55)
    print("SCRAPING FINISHED")
    print(f"Pages saved: {len(pages)}")
    print(
        "Courses extracted: "
        f"{len(course_page.get('courses', [])) if course_page else 0}"
    )
    print("Output: college_data.json")
    print("=" * 55)


if __name__ == "__main__":
    main()

