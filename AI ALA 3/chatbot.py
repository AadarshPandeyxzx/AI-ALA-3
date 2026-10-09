import json
import re
from pathlib import Path

DATA_FILE = Path(__file__).with_name("college_data.json")
WEBSITE = "https://gmiu.edu.in/gmiu/website/"


def load_college_data():
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


college_data = load_college_data()


def reload_data():
    global college_data
    college_data = load_college_data()
    return len(college_data)


def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9&.+\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text):
    text = (text or "").replace("\\n", " ").replace("\\t", " ")
    text = text.replace("\\", " ")
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(Home\s*>\s*)+", " ", text, flags=re.IGNORECASE)

    for phrase in (
        "skip to content", "main menu", "quick links", "show on map",
        "view more", "view pdf", "apply now", "read more", "360 virtual tour"
    ):
        text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    return text.strip(" |•-")


def get_courses():
    for page in college_data:
        if "courses_offered.php" in page.get("url", "").lower():
            courses = page.get("courses", [])
            if courses:
                return courses

    page = next(
        (p for p in college_data if "courses offered" in p.get("title", "").lower()),
        None,
    )
    if not page:
        return []

    pattern = re.compile(
        r"([A-Za-z][A-Za-z0-9 &()./,\-]{1,100}?)"
        r"\s+Duration\s*:\s*(\d+)\s*Years?"
        r"\s+Intake\s*:\s*(\d+)",
        re.IGNORECASE,
    )

    courses, seen = [], set()
    for name, duration, intake in pattern.findall(page.get("content", "")):
        name = re.sub(r"\s+", " ", name).strip(" -:;,")
        key = (name.casefold(), duration, intake)

        if len(name) < 3 or key in seen:
            continue

        seen.add(key)
        courses.append({
            "name": name,
            "duration": duration,
            "intake": intake,
        })

    return courses


def format_courses(courses, heading=None, limit=30):
    unique, seen = [], set()

    for course in courses:
        key = (
            course.get("name", "").casefold(),
            str(course.get("duration", "")),
            str(course.get("intake", "")),
        )

        if key not in seen:
            seen.add(key)
            unique.append(course)

    if not unique:
        return (
            "I couldn't find matching courses in the scraped data. "
            "Try another course name or run 'python scraper.py' again."
        )

    lines = [heading or f"Found {len(unique)} matching courses:"]

    for course in unique[:limit]:
        lines.append(
            f"• {course.get('name', 'Course name unavailable')} — "
            f"{course.get('duration', 'N/A')} years; "
            f"intake: {course.get('intake', 'N/A')}"
        )

    if len(unique) > limit:
        lines.append(
            f"...and {len(unique) - limit} more. "
            "Ask for a branch or specialization to narrow the list."
        )

    return "\n".join(lines)


def course_answer(message):
    courses = get_courses()

    if not courses:
        return "I couldn't load courses. Please run 'python scraper.py' first."

    q = normalize(message)
    q = re.sub(r"\b(parmacy|pharamacy|pharmcy)\b", "pharmacy", q)

    wants_btech = bool(re.search(
        r"\b(b\s*\.?\s*tech|btech|b\s*\.?\s*e\b|"
        r"bachelor of technology|bachelor of engineering)\b",
        q,
    ))
    wants_mtech = bool(re.search(
        r"\b(m\s*\.?\s*tech|mtech|master of technology)\b", q
    ))
    wants_diploma = "diploma" in q
    wants_pharmacy = "pharmacy" in q or "pharm" in q

    if wants_btech:
        results = [
            c for c in courses
            if str(c.get("duration", "")).strip() == "4"
            and "diploma" not in c.get("name", "").lower()
            and any(term in c.get("name", "").lower() for term in (
                "engineering",
                "information technology",
                "artificial intelligence",
                "data science",
            ))
        ]
        return format_courses(
            results,
            "Possible 4-year B.Tech / B.E. course entries:",
        )

    if wants_mtech:
        results = [
            c for c in courses
            if str(c.get("duration", "")).strip() == "2"
            and any(term in c.get("name", "").lower()
                    for term in ("engineering", "technology"))
        ]
        return format_courses(
            results,
            "Possible postgraduate engineering course entries:",
        )

    if wants_diploma:
        results = [
            c for c in courses
            if "diploma" in c.get("name", "").lower()
            or str(c.get("duration", "")).strip() == "3"
        ]
        return format_courses(results, "Diploma / three-year course entries:")

    if wants_pharmacy:
        results = [
            c for c in courses
            if "pharmacy" in c.get("name", "").lower()
            or "pharm" in c.get("name", "").lower()
        ]
        return format_courses(results, "Pharmacy course entries:")

    cleaned = re.sub(
        r"\b(show|me|all|list|give|tell|about|the|what|are|is|available|"
        r"offered|at|in|gmiu|college|university|course|courses|program|"
        r"programs|programme|programmes)\b",
        " ",
        q,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    compact = cleaned.replace(".", "").strip()

    aliases = {
        "it": ["information technology"],
        "ce": ["computer engineering"],
        "cse": ["computer science and engineering"],
        "computer": ["computer"],
        "ai ds": ["artificial intelligence", "data science"],
        "aids": ["artificial intelligence", "data science"],
        "aiml": ["artificial intelligence", "machine learning"],
        "ai ml": ["artificial intelligence", "machine learning"],
        "ec": ["electronics", "communication"],
        "mechanical": ["mechanical"],
        "civil": ["civil"],
        "chemical": ["chemical"],
        "electrical": ["electrical"],
        "bca": ["bca", "computer application"],
        "mca": ["mca", "computer application"],
        "bba": ["bba", "business administration"],
        "mba": ["mba", "business administration"],
    }

    if compact in aliases:
        terms = aliases[compact]
        results = []

        for course in courses:
            name = course.get("name", "").lower()

            if compact in ("ai ds", "aids", "aiml", "ai ml"):
                if all(term in name for term in terms):
                    results.append(course)
            elif any(term in name for term in terms):
                results.append(course)

        if compact == "it":
            return (
                "I found Information Technology course entries at different "
                "study levels. Ask for 'B.Tech IT', 'Diploma IT', or "
                "'Postgraduate IT' to narrow the results.\n\n"
                + format_courses(results)
            )

        return format_courses(results)

    branch_terms = [
        "computer science and engineering",
        "computer engineering",
        "information technology",
        "artificial intelligence",
        "electronics",
        "mechanical",
        "chemical",
        "civil engineering",
        "electrical engineering",
        "interior design",
        "computer application",
        "business administration",
        "aeronautical engineering",
    ]

    for term in branch_terms:
        if term in cleaned:
            return format_courses([
                c for c in courses
                if term in c.get("name", "").lower()
            ])

    if "undergraduate" in q or "under graduation" in q:
        results = [
            c for c in courses
            if str(c.get("duration", "")).strip() == "4"
            and "engineering" in c.get("name", "").lower()
        ]
        return format_courses(
            results,
            "Possible undergraduate engineering course entries:",
        )

    if "postgraduate" in q or "post graduation" in q:
        results = [
            c for c in courses
            if str(c.get("duration", "")).strip() == "2"
        ]
        return format_courses(results, "Possible postgraduate course entries:")

    return format_courses(courses)


def find_page_by_topics(topics):
    best_page, best_score = None, 0

    for page in college_data:
        title = page.get("title", "").lower()
        url = page.get("url", "").lower()
        content = page.get("content", "").lower()
        score = 0

        for topic in topics:
            topic = topic.lower()

            if topic in title:
                score += 10
            if topic in url:
                score += 8
            if topic in content:
                score += 1

        if score > best_score:
            best_page, best_score = page, score

    return best_page if best_score else None


def extract_sentences(content, keywords=None, limit=5):
    content = clean_text(content)
    parts = re.split(r"(?<=[.!?])\s+|(?=\b\d{1,2}\s+)", content)
    keywords = [k.lower() for k in (keywords or [])]

    selected, seen = [], set()

    for part in parts:
        sentence = re.sub(r"\s+", " ", part).strip(" |•-")

        if len(sentence) < 25:
            continue

        low = sentence.lower()

        if low in seen:
            continue
        seen.add(low)

        if keywords and not any(k in low for k in keywords):
            continue

        if sum(term in low for term in (
            "apply now", "show on map", "view pdf", "360 virtual tour"
        )) >= 2:
            continue

        selected.append(sentence)

        if len(selected) >= limit:
            break

    if selected:
        return " ".join(selected)

    fallback = content[:650].strip()
    return fallback + ("..." if len(content) > 650 else "")


def answer_from_pages(topics, keywords=None):
    page = find_page_by_topics(topics)

    if not page:
        return None

    title = clean_text(page.get("title", "")) or "GMIU Information"
    excerpt = extract_sentences(
        page.get("content", ""),
        keywords=keywords,
        limit=5,
    )

    return f"{title}\n\n{excerpt}" if excerpt else None


def contact_answer():
    return (
        "GMIU Contact Information\n\n"
        "Mobile: 7574949494\n"
        "Telephone: 9099951160\n"
        "Email: info@gmiu.edu.in\n"
        "Address: Sidsar Road, Bhavnagar, Gujarat 364060, India\n\n"
        "Course-wise counsellors:\n"
        "• Diploma: 87800 49651\n"
        "• B.Tech: 87800 89802\n"
        "• M.Tech: 87992 48026\n"
        "• B.Com / M.Com: 90236 67260\n"
        "• BBA / MBA: 70168 16678\n"
        "• BA / MA: 91064 34014\n"
        "• BCA / MCA / IT: 87996 75586\n\n"
        f"Website: {WEBSITE}"
    )


def placement_answer():
    page = find_page_by_topics([
        "training placement",
        "placement cell",
        "placement",
    ])

    if not page:
        return (
            "GMIU Training & Placement Cell\n\n"
            "I couldn't retrieve reliable placement statistics from the "
            "scraped data. For current placement updates, recruiter details, "
            "and placement support, visit:\n"
            f"{WEBSITE}"
        )

    content = clean_text(page.get("content", ""))

    section_match = re.search(
        r"(?:co[- ]?ordinators?|placement team)(.*?)(?:placement statistics|contact us|$)",
        content,
        flags=re.IGNORECASE,
    )
    section = section_match.group(1) if section_match else content

    name_pattern = re.compile(
        r"\b(?:Prof|Professor|Dr)\.?\s+"
        r"(?:[A-Z]\.\s*){0,2}[A-Z][a-z]+"
        r"(?:\s+(?:[A-Z]\.\s*){0,2}[A-Z][a-z]+){0,2}"
    )

    names = []
    for match in name_pattern.findall(section):
        name = re.sub(r"\s+", " ", match).strip(" .")

        if name.lower() not in {n.lower() for n in names}:
            names.append(name)

    lines = ["GMIU Training & Placement Cell"]

    if names:
        lines.append("\nCoordinator names found in the scraped page:")
        lines.extend(f"• {name}" for name in names[:10])
    else:
        excerpt = extract_sentences(
            content,
            ["placement", "training", "coordinator", "recruitment", "career"],
            3,
        )

        if excerpt and len(excerpt) > 450:
            excerpt = excerpt[:447].rsplit(" ", 1)[0] + "..."

        if excerpt:
            lines.append("\n" + excerpt)
        else:
            lines.append(
                "\nThe scraped page did not provide enough clean text to "
                "summarize placement statistics reliably. Please check the "
                "official website for current details."
            )

    lines.append(f"\nFor the latest placement information, visit:\n{WEBSITE}")
    return "\n".join(lines)


def admission_answer():
    return (
        "GMIU Admission — How to Apply\n\n"
        "1. Visit the official GMIU website.\n"
        "2. Open the Admissions section and choose the current admission cycle.\n"
        "3. Select Register/Login and create an account or sign in.\n"
        "4. Follow the application instructions and provide the requested details.\n"
        "5. Confirm course-specific eligibility, fees, required documents, "
        "and next steps with the university.\n\n"
        "The scraped page mentions the Admissions 2026 section, but links and "
        "dates can change. Verify the current instructions here:\n"
        f"{WEBSITE}"
    )


def fee_answer():
    return (
        "I couldn't find verified course-wise tuition fee amounts in the "
        "scraped data. Scholarship and EMI information is different from "
        "the actual course fee.\n\n"
        "For the latest fee structure, contact GMIU:\n"
        "Email: info@gmiu.edu.in\n"
        "Phone: 7574949494\n\n"
        f"Official website: {WEBSITE}"
    )


def find_answer(message):
    message = (message or "").strip()

    if not message:
        return "Please type a question."

    q = normalize(message)

    if re.search(
        r"\b(hi|hello|hey|hii|good morning|good afternoon|good evening)\b",
        q,
    ):
        return (
            "Hello! 👋 Welcome to the GMIU AI Assistant.\n\n"
            "Ask me about courses, admissions, fees, contact details, "
            "placements, or university information."
        )

    if re.search(r"\b(thanks|thank you|thank u|thx)\b", q):
        return "You're welcome! 😊 Let me know if you need anything else."

    if re.search(r"\b(bye|goodbye|see you)\b", q):
        return "Goodbye! 👋 Have a great day."

    if re.search(
        r"\b(contact|phone|telephone|email|address|location|helpline|"
        r"counsellor|counselor)\b",
        q,
    ):
        return contact_answer()

    if re.search(
        r"\b(scholarship|scholarships|financial aid|emi|installment|installments)\b",
        q,
    ):
        result = answer_from_pages(
            ["scholarships financial support", "scholarship", "financial support"],
            ["scholarship", "financial support", "emi", "installment"],
        )
        return result or (
            "I couldn't retrieve complete scholarship or EMI details from "
            "the scraped data. Please confirm eligibility and terms with GMIU:\n"
            f"{WEBSITE}"
        )

    if re.search(
        r"\b(fee|fees|tuition|cost|payment|semester fee|course fee|college fee)\b",
        q,
    ):
        return fee_answer()

    course_pattern = (
        r"\b(course|courses|program|programs|programme|programmes|degree|degrees|"
        r"diploma|bachelor|undergraduate|postgraduate|engineering|specialization|"
        r"specialisation|b\s*\.?\s*tech|m\s*\.?\s*tech|btech|mtech|b\s*\.?\s*e\b|"
        r"bca|mca|bba|mba|pharmacy|parmacy|pharamacy|pharmcy|computer engineering|"
        r"information technology)\b"
    )

    short_course_codes = {
        "it", "ce", "cse", "ec", "aids", "aiml",
        "btech", "mtech", "be", "bca", "mca", "bba", "mba",
    }

    if (
        re.search(course_pattern, q)
        or q.replace(".", "").replace(" ", "") in short_course_codes
    ):
        return course_answer(message)

    if re.search(
        r"\b(admission|admissions|apply|application|eligibility|"
        r"enroll|enrol|registration)\b",
        q,
    ):
        return admission_answer()

    if re.search(
        r"\b(placement|placements|job|jobs|career|recruitment|"
        r"company|companies|salary|internship)\b",
        q,
    ):
        return placement_answer()

    if re.search(
        r"\b(about|university|college|gmiu|campus|facilities|hostel|"
        r"transport|transportation|chairman|provost|recognition)\b",
        q,
    ):
        result = answer_from_pages(
            ["about gmiu", "university", "about us", "campus"],
            ["university", "campus", "education", "facilities", "gmiu"],
        )
        if result:
            return result

    keywords = [word for word in q.split() if len(word) > 2]
    result = answer_from_pages(keywords, keywords)

    if result:
        return result

    return (
        "Sorry, I couldn't find that information in the scraped college data.\n\n"
        "Try asking about courses, admissions, fees, contact details, "
        "placements, or university information."
    )