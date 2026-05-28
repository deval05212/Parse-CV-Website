import argparse
import re
from typing import Optional, Tuple
from pathlib import Path


MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12"
}


def standardize_dates(text: str) -> str:
    months_pattern = "|".join(MONTH_MAP.keys())
    
    # 0. Remove date artifacts: "15th of", "the mid-", etc.
    text = re.sub(r"(?i)\b(\d+(?:st|nd|rd|th)?)\s+(?:of|in)\b", " ", text)
    text = re.sub(r"(?i)\b(?:the|mid|early|late)[-\s]+", " ", text)

    # 1. Match Day Month Year: "25 July 1978" -> "1978-07-25"
    day_month_year = rf"\b(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})\b"
    def replace_dmy(match):
        day = match.group(1).zfill(2)
        month = match.group(2).lower()
        year = match.group(3)
        return f"{year}-{MONTH_MAP[month]}-{day}"
    text = re.sub(day_month_year, replace_dmy, text, flags=re.IGNORECASE)

    # 2. Match Month Range with Year: "Jan - Feb 2020" -> "2020-01 - 2020-02"
    range_pattern = rf"\b({months_pattern})\b\s*([-–—to\s]+)\s*\b({months_pattern})\b\s+(\d{{4}})"
    def replace_range(match):
        m1 = match.group(1).lower()
        sep = match.group(2)
        m2 = match.group(3).lower()
        year = match.group(4)
        return f"{year}-{MONTH_MAP[m1]} {sep} {year}-{MONTH_MAP[m2]}"
    text = re.sub(range_pattern, replace_range, text, flags=re.IGNORECASE)

    # 3. Match Single Month Year: "Jan 2020" -> "2020-01"
    single_pattern = rf"\b({months_pattern})\s+(\d{{4}})\b"
    def replace_single(match):
        month = match.group(1).lower()
        year = match.group(2)
        return f"{year}-{MONTH_MAP[month]}"
    text = re.sub(single_pattern, replace_single, text, flags=re.IGNORECASE)
    
    return text


def fix_ocr_errors(text: str) -> str:
    # Fix common OCR errors in years like 202], 202l, 202I, 202!
    # Remove trailing \b because it fails when the error char itself is non-word (like ']')
    text = re.sub(r"\b20[12][\]lI!](?!\w)", lambda m: m.group(0)[:-1] + "1", text)
    # Fix broken email symbols
    # Keep this within a single line to avoid false matches like "Surat \n linkedin.com"
    text = re.sub(
        r"([a-zA-Z0-9._%+-]+)[^\S\r\n]*\bat\b[^\S\r\n]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        r"\1@\2",
        text,
        flags=re.IGNORECASE,
    )
    return text


def merge_phone_numbers(text: str) -> str:
    # Match phone-like patterns (restrict spacing to horizontal space and tab to prevent multi-line matching)
    pattern = r"(?:\+(?:[\s\t]*\(?)?\d[\d \t\-\(\)]{8,}\d|\(?\d[\d \t\-\(\)]{8,}\d)"

    def replace_phone(match):
        phone = match.group(0)

        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        # Handle OCR-noise: if 11 digits and starts with a digit that is not 0 or 1,
        # and the second digit starts with 6,7,8,9 (e.g. "2 9909852385" -> "9909852385")
        if len(digits) == 11 and digits[0] not in "01" and digits[1] in "6789":
            digits = digits[1:]
        # Handle trunk prefix: if 11 digits and starts with 0, strip it
        elif len(digits) == 11 and digits[0] == "0":
            digits = digits[1:]

        # Indian mobile validation
        if len(digits) == 10 and digits[0] in "6789":
            digits = "91" + digits

        # Convert to +91 format
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits

        # Preserve / prepend "+" if original had "+" or we have a country code
        if phone.strip().startswith("+") or (len(digits) > 10 and not digits.startswith("0")):
            return "+" + digits

        # Keep original if invalid
        return phone

    return re.sub(pattern, replace_phone, text)


def normalize_headers(text: str) -> str:
    header_map = {
        # EXPERIENCE
        "experience": "EXPERIENCE",
        "experiences": "EXPERIENCE",
        "professional experience": "EXPERIENCE",
        "professional experiences": "EXPERIENCE",
        "work experience": "EXPERIENCE",
        "work experiences": "EXPERIENCE",
        "employment history": "EXPERIENCE",
        "work history": "EXPERIENCE",
        "professional background": "EXPERIENCE",
        "employment": "EXPERIENCE",
        "career history": "EXPERIENCE",
        "professional work experience": "EXPERIENCE",
        "work experience / freelance": "EXPERIENCE",
        
        # EDUCATION
        "education": "EDUCATION",
        "educations": "EDUCATION",
        "academic background": "EDUCATION",
        "educational qualification": "EDUCATION",
        "educational qualifications": "EDUCATION",
        "academic profile": "EDUCATION",
        "academics": "EDUCATION",
        "academic credentials": "EDUCATION",
        "my educations": "EDUCATION",
        "educational background": "EDUCATION",
        
        # SKILLS
        "skills": "SKILLS",
        "technical skills": "SKILLS",
        "key skills": "SKILLS",
        "skills / technologies": "SKILLS",
        "core skills": "SKILLS",
        "professional skills": "SKILLS",
        "skills and technologies": "SKILLS",
        "technical expertise": "SKILLS",
        
        # PROJECTS
        "projects": "PROJECTS",
        "personal projects": "PROJECTS",
        "academic projects": "PROJECTS",
        "key projects": "PROJECTS",
        "projects and achievements": "PROJECTS",
        "project work": "PROJECTS",
        
        # CERTIFICATES
        "certifications": "CERTIFICATES",
        "certificates": "CERTIFICATES",
        "certifications and licenses": "CERTIFICATES",
        "courses": "CERTIFICATES",
        "training": "CERTIFICATES",
        "training and certifications": "CERTIFICATES",
        
        # SUMMARY
        "professional summary": "SUMMARY",
        "summary": "SUMMARY",
        "profile": "SUMMARY",
        "personal details": "PERSONAL DETAILS",
    }
    
    lines = text.split("\n")
    new_lines = []
    for line in lines:
        stripped = line.strip().lower().rstrip(":")
        if stripped in header_map:
            new_lines.append(header_map[stripped] + ":")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def clean_urls(text: str) -> str:
    # Remove trailing punctuation from common social links
    def strip_link_noise(match):
        return match.group(0).rstrip(".,)]")
    
    url_pattern = r"https?://(?:www\.)?[\w\-\.]+\.[a-z]{2,}(?:/[\w\-\.]*)*"
    return re.sub(url_pattern, strip_link_noise, text, flags=re.I)


def fix_broken_urls(text: str) -> str:
    """Repairs OCR-broken URL patterns like 'h ps://', 'h ps : //', etc."""
    # h ps://..., h ttp://..., with optional spaces around separators
    text = re.sub(r"(?i)\bh\s*t\s*t\s*p\s*s?\s*:\s*/\s*/", lambda m: "https://" if "s" in m.group(0).lower() else "http://", text)
    text = re.sub(r"(?i)\bh\s*p\s*s?\s*:\s*/\s*/", lambda m: "https://" if "s" in m.group(0).lower() else "http://", text)
    # Common OCR break: https:/example.com (single slash)
    text = re.sub(r"(?i)\bhttps?:/(?!/)", lambda m: m.group(0) + "/", text)
    return text


INVALID_SOCIAL_TOKENS = {
    "summary", "experience", "education", "skills", "projects", "profile",
    "github", "linkedin", "languages", "language", "contact", "portfolio",
    "website", "link", "links", "aws", "gitlab", "postman", "copilot",
}


def is_invalid_social_handle(handle: str) -> bool:
    cleaned = handle.strip().strip("/").lower()
    if len(cleaned) < 3:
        return True
    if cleaned in INVALID_SOCIAL_TOKENS:
        return True
    if cleaned.startswith("-") or cleaned.endswith("-"):
        return True
    return False


def normalize_social_url(url: str) -> Optional[Tuple[str, str]]:
    """Returns normalized (label, url) for social links, else None."""
    cleaned = url.strip().rstrip(".,);:]")
    if not re.match(r"(?i)^https?://", cleaned):
        cleaned = "https://" + cleaned.lstrip("/")

    lower_url = cleaned.lower()

    if "linkedin.com" in lower_url:
        match = re.search(r"linkedin\.com/(?:in/)?([a-z0-9][a-z0-9._-]{1,99})/?$", lower_url)
        if not match:
            return None
        handle = match.group(1).strip("._-")
        if is_invalid_social_handle(handle):
            return None
        return "LinkedIn", f"https://www.linkedin.com/in/{handle}"

    if "github.com" in lower_url:
        match = re.search(r"github\.com/([a-z0-9][a-z0-9-]{1,38})(?:/[^\s]*)?$", lower_url)
        if not match:
            return None
        handle = match.group(1).strip("-")
        if is_invalid_social_handle(handle):
            return None
        return "GitHub", cleaned

    return None


def structure_contact_info(text: str) -> str:
    def expand_linkedin(match):
        handle = match.group(1).strip().strip("/")
        if is_invalid_social_handle(handle):
            return ""
        return f"LinkedIn: https://www.linkedin.com/in/{handle}"

    def expand_github(match):
        handle = match.group(1).strip().strip("/")
        if is_invalid_social_handle(handle):
            return ""
        return f"GitHub: https://github.com/{handle}"

    # Expand handle-only social lines into full URLs with strict validation.
    text = re.sub(r"(?im)^\s*linkedin\s*[:\-]?\s*([a-z0-9._-]{3,})\s*$", expand_linkedin, text)
    text = re.sub(r"(?im)^\s*github\s*[:\-]?\s*([a-z0-9._-]{3,})\s*$", expand_github, text)

    lines = text.splitlines()
    new_lines = []

    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    url_pattern = r"(?:https?://|www\.)[^\s]+|(?:linkedin\.com(?:/[^\s]*)?|github\.com(?:/[^\s]*)?)"
    placeholder_lines = {
        "linkedin",
        "github",
        "portfolio",
        "linkedin github",
        "linkedin github portfolio",
        "linkedin: github:",
    }

    for line in lines:

        # Extract emails
        emails = re.findall(email_pattern, line)

        # Extract URLs
        urls = re.findall(url_pattern, line)

        # Remove extracted data from original line
        cleaned_line = line

        for email in emails:
            cleaned_line = cleaned_line.replace(email, "").strip()

        for url in urls:
            cleaned_line = cleaned_line.replace(url, "").strip()

        normalized_cleaned = cleaned_line.lower().strip(" :-")

        # Keep remaining text (except placeholder-only lines)
        if cleaned_line and normalized_cleaned not in placeholder_lines:
            new_lines.append(cleaned_line)

        # Add formatted emails
        for email in emails:
            new_lines.append(f"Email: {email}")

        # Dynamically detect URL type
        for url in urls:
            social = normalize_social_url(url)
            if social is not None:
                label, normalized_url = social
                new_lines.append(f"{label}: {normalized_url}")
                continue

            normalized_url = url.strip().rstrip(".,);:]")
            if not re.match(r"(?i)^https?://", normalized_url):
                normalized_url = "https://" + normalized_url.lstrip("/")

            lower_url = normalized_url.lower()
            if "linkedin.com" in lower_url or "github.com" in lower_url:
                # If social-domain URL is malformed/invalid, drop it instead of treating as generic website.
                continue

            host_match = re.match(r"(?i)^https?://([^/\s]+)", normalized_url)
            if not host_match:
                continue
            if "." not in host_match.group(1).strip("."):
                continue

            if "tryhackme.com" in lower_url:
                label = "TryHackMe"
            elif "hackerrank.com" in lower_url:
                label = "HackerRank"
            elif "leetcode.com" in lower_url:
                label = "LeetCode"
            elif "portfolio" in lower_url:
                label = "Portfolio"
            else:
                label = "Website"

            new_lines.append(f"{label}: {normalized_url}")

    return "\n".join(new_lines)


def normalize_present_ranges(text: str) -> str:
    """Normalizes date ranges ending in present/current."""
    # 2025-08 Current -> 2025-08 - Present
    text = re.sub(r"(?i)\b(\d{4}-\d{2})\s*(?:-|–|—|to)?\s*(present|current)\b", r"\1 - Present", text)
    # 08/2025 present -> 08/2025 - Present
    text = re.sub(r"(?i)\b(\d{2}/\d{4})\s*(?:-|–|—|to)?\s*(present|current)\b", r"\1 - Present", text)
    # 2025 present -> 2025 - Present
    text = re.sub(r"(?i)\b(\d{4})\s*(?:-|–|—|to)\s*(present|current)\b", r"\1 - Present", text)
    return text


def fix_spaced_out_text(text: str) -> str:
    """Fixes text where OCR has inserted spaces between every letter (e.g., S I N G H -> SINGH)."""
    # Matches a capital letter followed by a space, repeated at least twice, ending with a capital letter.
    # We use a lookahead to ensure we don't accidentally join 'A B' in a sentence unless it's part of a longer sequence.
    def join_chars(match):
        return match.group(0).replace(" ", "")
    
    # Pattern: A B C D -> ABCD. Requires at least 3 letters to be safe, or 2 if they are part of a longer string.
    # We'll use a simpler approach: join any sequence of [SingleCap Space SingleCap]
    # provided it happens multiple times or is followed by another single cap.
    # Pattern: A B C D -> ABCD or 2 0 2 1 -> 2021.
    # Matches any alphanumeric character followed by EXACTLY one horizontal space, 
    # if it's between other alphanumeric characters. This preserves double spaces between words.
    text = re.sub(r'(?<=\b[A-Z0-9])[ \t]{1}(?=[A-Z0-9]\b)', '', text)
    return text


def fix_concatenated_years(text: str) -> str:
    """Splits mashed years like 20212023 or 202120232025 into 2021 - 2023 - 2025."""
    # Matches a year (19xx or 20xx) followed immediately by another year.
    # We remove \b to allow matching inside mashed strings.
    return re.sub(r'(20\d{2}|19\d{2})(?=(20\d{2}|19\d{2}))', r'\1 - ', text)


def separate_mashed_headers(text: str) -> str:
    """Separates section headers that are mashed together (e.g., EDUCATIONSKILLS -> EDUCATION SKILLS)."""
    headers = [
        "EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS", "SUMMARY", 
        "CONTACT", "LANGUAGES", "CERTIFICATES", "PROFILE", "PERSONAL"
    ]
    pattern = rf"({'|'.join(headers)})(?=[A-Z])"
    return re.sub(pattern, r"\1 ", text)


def remove_boilerplate(text: str) -> str:
    """Removes common resume template noise and calls to action."""
    noise = [
        r"(?i)For more details,?\s*Please visit my linkedin profile\.?",
        r"(?i)live at\s*:\s*https?://\S+",
        r"(?i)This Free Resume Template is the copyright of Qwikresume\.com",
        r"(?i)This free resume template is the copyright of Novoresume\.com",
    ]
    for pattern in noise:
        text = re.sub(pattern, "", text)
    return text


TYPO_FIXES = {
    r"\bMisrosoft\b": "Microsoft",
    r"\bAssociats\b": "Associates",
    r"\bE-Mait\b": "E-Mail",
    r"\bJou mal\b": "Journal",
    r"\bAccountanat\b": "Accountant",
    r"\bAccountat\b": "Accountant",
    r"\bmat-tasking\b": "multi-tasking",
    r"\bPeach tree\b": "Peachtree",
    r"\bPandL\b": "P and L",
    r"\bResponsib\s+ies\b": "Responsibilities",
    r"\bQualificati\s+ons\b": "Qualifications",
    # OCR specific fixes
    r"\bDV\s*L\s*P\s*R\b": "Developer",
    r"\bS\s*F\s*T\s*W\s*A\s*R\b": "Software",
    r"\bW\s*R\s*K\s*X\s*E\s*R\s*I\s*N\s*E\b": "EXPERIENCE",
    r"\bL\s*A\s*N\s*G\s*U\s*A\s*G\s*S\b": "LANGUAGES",
    r"\bS\s*U\s*M\s*A\s*R\s*Y\b": "SUMMARY",
    r"\bF\s*U\s*L\s*L\s*-\s*S\s*T\s*A\s*K\b": "Full-Stack",
    r"\bD\s*U\s*A\s*T\s*I\s*N\b": "DURATION",
    r"\bV\s*I\s*D\s*Y\s*A\s*S\s*A\s*N\s*K\s*U\s*L\b": "Vidya Sankul",
    r"\bLinkedln\b": "LinkedIn",
}


def normalize_fragmented_headers(text: str) -> str:
    """Normalizes section headers that are broken into spaced syllables/fragments."""
    # We require a mandatory space (\\s+) after the first segment to prevent matching normal words.
    # 1. Experience: x pe ri en ce, e x p e r i e n c e
    text = re.sub(
        r"(?i)\b(?:e\s+x\s*p\s*e\s*r\s*i\s*e\s*n\s*c\s*e|x\s+p\s*e\s*r\s*i\s*e\s*n\s*c\s*e)\b",
        "\nEXPERIENCE\n",
        text
    )
    # 2. Skills: S k i ll s, s k i l l s
    text = re.sub(
        r"(?i)\bs\s+k\s*i\s*l\s*l\s*s\b",
        "\nSKILLS\n",
        text
    )
    # 3. Education: du c at ion, e d u c a t i o n
    text = re.sub(
        r"(?i)\b(?:e\s+d\s*u\s*c\s*a\s*t\s*i\s*o\s*n|d\s+u\s*c\s*a\s*t\s*i\s*o\s*n)\b",
        "\nEDUCATION\n",
        text
    )
    # 4. Projects: ro je ct s, p r o j e c t s
    text = re.sub(
        r"(?i)\b(?:p\s+r\s*o\s*j\s*e\s*c\s*t\s*s|r\s+o\s*j\s*e\s*c\s*t\s*s)\b",
        "\nPROJECTS\n",
        text
    )
    # 5. Achievements: A c hi ev e me nt s, a c h i e v e m e n t s
    text = re.sub(
        r"(?i)\ba\s+c\s*h\s*i\s*e\s*v\s*e\s*m\s*e\s*n\s*t\s*s\b",
        "\nACHIEVEMENTS\n",
        text
    )
    return text


def clean_text(text: str, lowercase: bool = False) -> str:
    # 0. Advanced OCR & Formatting Fixes
    text = normalize_fragmented_headers(text)
    text = fix_spaced_out_text(text)
    text = fix_concatenated_years(text)
    text = separate_mashed_headers(text)
    text = remove_boilerplate(text)
    text = fix_ocr_errors(text)

    # 1. Horizontal lines and bullet markers
    text = re.sub(r"_{3,}", "", text)
    text = re.sub(r"-{3,}", "", text)
    # Remove repetitive single-character dividers
    text = re.sub(r"[\.\-]{5,}", " ", text)
    
    # Remove emojis and special Unicode symbols
    text = re.sub(r'[^\x00-\x7f]', ' ', text)
    # Replace bullet markers with spaces to avoid merging words
    text = re.sub(r"[•⚫■★\*·❘\uf0b7\u2714\u2708\ufe0f\u2705]", " ", text)
    
    # 1.5 Header Normalization
    text = normalize_headers(text)

    # 2. Aggressive Label & Noise Removal (C, E, M, P, O)
    # ... (remains same) ...
    text = re.sub(r"(?m)^\s*[CEMPO]\s*[:\-]\s*", " ", text)
    text = re.sub(r"\s+\b[CEMPO]\b\s+", " ", text)
    
    # 3. Spelling Correction
    for pattern, replacement in TYPO_FIXES.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # 4. Standardize Symbols
    text = text.replace("&", " and ")
    text = text.replace("|", " ")

    # 4.2 URL repairs before contact extraction
    text = fix_broken_urls(text)
    
    # 4.5 URL Cleaning
    text = structure_contact_info(text)
    
    # Standardize slashes only if they already have spaces or are isolated
    text = re.sub(r"(?<=\s)/(?=\s)", " / ", text)
    
    # 5. Noise Tokens & Footers
    text = re.sub(r"(?i)Page \d+ of \d+", "", text)
    text = re.sub(r"(?i)Nnovoresume\.com", "", text)
    text = re.sub(r"(?i).*This Free Resume Template.*", "", text)
    text = re.sub(r"(?i).*qwikresume.*", "", text)
    
    # 6. Phone Number Merging
    text = merge_phone_numbers(text)
    
    # 7. Date Standardization
    text = standardize_dates(text)
    text = normalize_present_ranges(text)
    
    # 8. Fix artifacts and duplicates
    text = text.replace("mailto:", "")
    text = re.sub(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\1", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

    # 9. Skill Rating Noise
    # Remove common 'skill bar' artifacts (eee, eeee, eceoee)
    text = re.sub(r"\b[eE]{2,6}\b", " ", text)
    text = re.sub(r"\bece?o?e?e\b", " ", text, flags=re.IGNORECASE)

    # 10. Normalize Whitespace (Keep Newlines)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    
    # 11. Final Cleanup within lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?im)^(Email|LinkedIn|GitHub|Portfolio|Website):\s*$", "", text)
    text = re.sub(r"(?im)^Email:\s+Phone:\s*", "Phone: ", text)
    text = re.sub(r"(?im)^LinkedIn\s+GitHub(?:\s+Portfolio)?\s*$", "", text)
    text = re.sub(r"(?im)^LinkedIn\s+GitHub\s+", "", text)
    text = re.sub(r"(?im)^in\s*$", "", text)
    text = re.sub(r"(?im)^LinkedIn:\s*GitHub:\s*$", "", text)
    text = re.sub(r"(?im)\s+Portfolio:\s*$", "", text)
    text = re.sub(r"(?im)^Link$", "", text)

    # Remove single non-alphanumeric character noise at the start/end of lines
    # (But keep common punctuation like %, ., !, ?, ), ], :, etc. and '+' followed by digits)
    text = re.sub(r"(?m)^(?!\+\d)[^\w\s\(\[\{]\s*", "", text)
    # Whitelist more trailing characters that are meaningful in resumes
    text = re.sub(r"(?m)\s*[^a-zA-Z0-9\s%\.\?!,;:\)\]\-\+\u00B0]$", "", text)

    if lowercase:
        text = text.lower()

    return text.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean all resume text files")
    parser.add_argument("--resume-dir", default="Assets/resumes", help="Folder containing resume .txt files")

    # This is for the output directory, not output_dir1
    parser.add_argument("--output-dir", default="Assets/resume_clean_dataset", help="Folder to save cleaned files")
    parser.add_argument("--lowercase", action="store_true", help="Convert text to lowercase")
    args = parser.parse_args()

    resume_dir = Path(args.resume_dir)
    output_dir = Path(args.output_dir)
    
    if not resume_dir.exists():
        raise FileNotFoundError(f"Resume directory not found: {resume_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(resume_dir.glob("*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
    if not files:
        raise SystemExit(f"No .txt files found in {resume_dir}")

    print(f"Cleaning {len(files)} files from {resume_dir} → {output_dir}")

    for path in files:
        original = path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_text(original, lowercase=args.lowercase)
        
        out_path = output_dir / path.name
        out_path.write_text(cleaned, encoding="utf-8")

    print(f"Successfully cleaned all files.")
    print(f"Lowercase applied: {args.lowercase}")


if __name__ == "__main__":
    main()
