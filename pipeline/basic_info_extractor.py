import re
from pathlib import Path

# Email Regex
EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)

# Phone Regex (only match spaces and tabs, not newlines)
PHONE_RE = re.compile(
    r'(?<![\w@])(?:\+?\d[\d \t\-\.\(\)]{6,14}\d)(?![\w@])'
)

# Words commonly found in resume texts/filenames that are not part of the candidate's name
INVALID_WORDS = {
    # Job titles / roles / general professional terms
    "developer", "designer", "executive", "analyst", "specialist", 
    "manager", "engineer", "consultant", "intern", "student", 
    "administrator", "lead", "architect", "officer", "bde", "sdr", "bdr", "hr",
    "expert", "professional", "programmer", "coder", "representative", "specialists",
    "fresher", "trainee", "associate", "associates",
    
    # Educational institutions & degrees
    "university", "college", "school", "academy", "institute", "vidhyalay", 
    "vidhyabhavan", "collage", "vidyabhavan", "vidya", "sankul", "narmad", "vnsgu",
    "collag", "inst", "dept", "department", "hsc", "ssc", "mca", "bca", "be", "btech",
    "mtech", "mba", "bcom", "mcom", "phd", "diploma", "degree",
    
    # Corporate suffix / general business terms
    "pvt", "ltd", "solutions", "services", "technologies", "systems", "infotech", "llp",
    "company", "corporation", "industries", "group", "enterprise", "enterprises",
    
    # Section headers / resume terms
    "profile", "objective", "summary", "experience", "education", "skills", 
    "projects", "certifications", "languages", "hobbies", "interests", "contact",
    "about", "me", "resume", "cv", "curriculum", "vitae", "details", "personal",
    "career", "declaration", "information", "hometown", "address", "phone", "email",
    "gender", "nationality", "hobbies", "languages", "known"
}

INVALID_EXACT_NAMES = {
    "surat", "gujarat", "bhopal", "pune", "india", "mumbai", "linkedin", "github", "portfolio", "website", "email",
    "about me", "personal details", "career objective", "curriculum vitae", "contact me"
}

NOISE_WORDS = INVALID_WORDS.union({"resume", "cv", "updated", "premium", "placement", "new", "update", "copy", "and", "exe", "final"})

INVALID_LOC_WORDS = {
    "university", "college", "school", "institute", "institude", "academy",
    "education", "experience", "skills", "projects", "certifications",
    "languages", "hobbies", "placement", "internship", "intern"
}


def extract_email_phone(text):
    result = {
        "email": "",
        "phone": ""
    }

    # Extract Email
    email_matches = EMAIL_RE.findall(text)
    if email_matches:
        result["email"] = email_matches[0]

    # Extract Phone Numbers
    phone_matches = PHONE_RE.findall(text)

    # Clean invalid numbers
    phone_matches = [
        p.strip()
        for p in phone_matches
        if len(re.sub(r'\D', '', p)) >= 7
        and not re.search(r'\d{4}[\s\-/]{1,3}\d{4}', p.strip())
        and not p.strip().startswith(('20', '19'))
        and '\n' not in p and '\r' not in p
    ]

    if phone_matches:
        result["phone"] = phone_matches[0]

    return result


def extract_social_links(text):
    result = {
        "linkedin": "",
        "github": ""
    }

    # LinkedIn Regex
    linkedin_match = re.search(
        r'(?:https?://)?(?:www\.)?linkedin\.com/in/([\w\-]+)',
        text,
        re.I
    )

    if linkedin_match:
        result["linkedin"] = linkedin_match.group(0)

    # GitHub Regex
    github_match = re.search(
        r'(?:https?://)?(?:www\.)?github\.com/([\w\-]+)',
        text,
        re.I
    )

    if github_match:
        result["github"] = github_match.group(0)

    return result


def clean_extracted_name(name: str) -> str:
    """Cleans up the extracted name from GLiNER to remove formatting noise."""
    if not name:
        return ""
    # Remove newlines and multiple spaces
    name = re.sub(r'\s+', ' ', name)
    # Remove trailing/leading punctuation/symbols
    name = name.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
    # If the name is all uppercase or lowercase, title-case it nicely
    if name.isupper() or name.islower():
        name = name.title()
    return name


def clean_location(loc: str) -> str:
    """Cleans up location text by removing extra whitespaces and punctuation."""
    loc = re.sub(r'\s+', ' ', loc)
    loc = loc.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
    return loc


CITIES_LIST = [
    "Surat", "Vadodara", "Baroda", "Ahmedabad", "Rajkot", "Gandhinagar", "Anand", "Pune", 
    "Mumbai", "Bombay", "Bhopal", "Delhi", "Noida", "Navsari", "Valsad", "Nadiad", "Bharuch"
]


def search_geo_fallback(text: str) -> str:
    """Scans the text for common cities from CITIES_LIST and returns the first matched city."""
    text_chunk = text[:1000]
    for city in CITIES_LIST:
        pattern = rf"\b{city}\b"
        match = re.search(pattern, text_chunk, re.IGNORECASE)
        if match:
            return city
            
    regions = ["Gujarat", "Maharashtra", "Madhya Pradesh", "India"]
    for reg in regions:
        pattern = rf"\b{reg}\b"
        match = re.search(pattern, text_chunk, re.IGNORECASE)
        if match:
            return reg
            
    return ""


def extract_location(text: str, model, candidate_name: str, threshold: float = 0.35) -> str:
    """Extracts candidate location using GLiNER with merging and candidate-name filtering."""
    if not text:
        return ""
        
    # Check first 300 characters first for candidate's home location
    header_chunk = text[:300]
    
    # Pre-clean some common icon/noise terms in the header chunk to help GLiNER
    clean_chunk = re.sub(
        r'(?i)\b(map-marker(?:-alt)?|phone(?:-alt)?|envelope|email|github|linkedin|location|address)\b',
        ' ',
        header_chunk
    )
    
    entities = model.predict_entities(clean_chunk, labels=["location", "city", "country"], threshold=threshold)
    
    # Fallback to first 1000 characters if nothing found in first 300
    if not entities:
        entities = model.predict_entities(text[:1000], labels=["location", "city", "country"], threshold=threshold)
        
    if not entities:
        geo_city = search_geo_fallback(text)
        if geo_city:
            return geo_city
        return ""
        
    # Sort by start index
    entities = sorted(entities, key=lambda x: x['start'])
    
    # Merge nearby entities (e.g., within 15 characters of each other)
    merged_groups = []
    current_group = []
    
    for ent in entities:
        ent_text = clean_location(ent['text'])
        if not ent_text:
            continue
        
        # Avoid duplicate / sub-string entities
        if current_group:
            last_ent = current_group[-1]
            # If this entity overlaps or is a duplicate, skip
            if ent['start'] >= last_ent['start'] and ent['end'] <= last_ent['end']:
                continue
            if ent_text.lower() in [x['text'].lower() for x in current_group]:
                continue
                
            # If distance is small, merge
            distance = ent['start'] - last_ent['end']
            if distance <= 15:
                current_group.append(ent)
            else:
                merged_groups.append(current_group)
                current_group = [ent]
        else:
            current_group = [ent]
            
    if current_group:
        merged_groups.append(current_group)
        
    if not merged_groups:
        geo_city = search_geo_fallback(text)
        if geo_city:
            return geo_city
        return ""
        
    # We prefer the first group of locations, especially if it's near the top
    best_group = merged_groups[0]
    
    # Form the location string and filter out parts matching the candidate name
    candidate_words = set(candidate_name.lower().split()) if candidate_name else set()
    loc_parts = []
    
    for ent in best_group:
        cleaned = clean_location(ent['text'])
        if not cleaned:
            continue
            
        cleaned_lower = cleaned.lower()
        
        # Filter if the part is exactly the candidate's name or a subset of candidate's name words
        if candidate_name and cleaned_lower == candidate_name.lower():
            continue
            
        p_words = set(cleaned_lower.split())
        if p_words and candidate_words and p_words.issubset(candidate_words):
            continue
            
        # Filter if the part contains any education/experience keywords to avoid universities/companies
        p_words_clean = {w.strip(".,;:()") for w in cleaned_lower.split()}
        if any(w in INVALID_LOC_WORDS for w in p_words_clean):
            continue
            
        if cleaned not in loc_parts:
            # Title case if all upper or all lower
            if cleaned.isupper() or cleaned.islower():
                cleaned = cleaned.title()
            loc_parts.append(cleaned)
            
    if not loc_parts:
        geo_city = search_geo_fallback(text)
        if geo_city:
            return geo_city
        return ""
        
    return ", ".join(loc_parts)


def is_valid_person_name(name: str) -> bool:
    """Validates if a string is a plausible candidate name (excludes roles/schools/etc.)."""
    if not name:
        return False
    name_clean = clean_extracted_name(name)
    name_lower = name_clean.lower()
    
    # 1. Length checks
    if len(name_clean) <= 2 or len(name_clean) > 40:
        return False
        
    # 2. Exact match check
    if name_lower in INVALID_EXACT_NAMES:
        return False
        
    # 3. Check for digits
    if any(c.isdigit() for c in name_clean):
        return False
        
    # 4. Check word count
    words = name_lower.split()
    if len(words) > 5:
        return False
        
    # 5. Check if any word is in the invalid list
    for w in words:
        w_clean = w.strip(".,;:()")
        if w_clean in INVALID_WORDS:
            return False
            
    # 6. Must contain at least one alphabetic character
    if not any(c.isalpha() for c in name_clean):
        return False
        
    return True


def extract_name_from_filename(filename: str) -> str:
    """Fallback function to parse candidate name from the filename itself."""
    stem = Path(filename).stem
    # Remove leading timestamp or ID digits if any (e.g. 1767590903517-Vidhi_Mavani_Resume -> Vidhi_Mavani_Resume)
    stem = re.sub(r'^\d+[-_]?', '', stem)
    # Split camelCase / PascalCase
    stem = re.sub(r'([a-z])([A-Z])', r'\1 \2', stem)
    # Split by common delimiters
    parts = re.split(r'[-_\s\(\)]+', stem)
    
    cleaned_parts = []
    for p in parts:
        if not p:
            continue
        if p.isdigit(): # Skip years or versions
            continue
        p_lower = p.lower()
        if p_lower in NOISE_WORDS:
            continue
        # Clean up any trailing/leading punctuation
        p_clean = p.strip(".,;:()")
        if p_clean:
            cleaned_parts.append(p_clean)
            
    name = " ".join(cleaned_parts).strip()
    return name.title() if name else ""


JOB_KEYWORDS = [
    "developer", "engineer", "analyst", "designer", "specialist", 
    "manager", "lead", "architect", "consultant", "executive", 
    "intern", "trainee", "associate", "expert", "programmer", 
    "coder", "administrator", "officer", "bde", "sdr", "bdr", "hr",
    "qa", "quality assurance", "specialists", "professional"
]

FILENAME_KEYWORDS = JOB_KEYWORDS + [
    "stack", "frontend", "backend", "android", "ios", "flutter", 
    "devops", "ai", "ml", "data science", "data scientist", "sales", 
    "marketing", "python", "java", "php", "react"
]


def clean_role(role: str) -> str:
    if not role:
        return ""
    # Remove leading/trailing non-alphanumeric except common title chars
    role = re.sub(r'\s+', ' ', role)
    # Strip common noise and parentheses if they are unmatched or empty
    role = role.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★+&")
    
    # Strip trailing noise words
    trailing_noise = {"with", "for", "at", "to", "in", "and", "from", "on", "by", "as", "of", "role", "profile"}
    while True:
        words = role.split()
        if not words:
            break
        if words[-1].lower() in trailing_noise:
            role = " ".join(words[:-1])
        else:
            break

    # Strip cities/states from role
    for geo in ["surat", "gujarat", "ahmedabad", "pune", "mumbai", "india", "bhopal", "delhi", "noida", "vadodara", "baroda"]:
        role = re.sub(rf'\b{geo}\b', '', role, flags=re.IGNORECASE)
        
    # remove words containing digits
    words = role.split()
    words_clean = [w for w in words if not any(c.isdigit() for c in w)]
    role = " ".join(words_clean)

    # clean spaces and punctuation again
    role = re.sub(r'\s+', ' ', role).strip(" \t\n\r.,;:-|/()[]{}*•⚫■★+&")

    # Clean up unmatched brackets
    if role.count("(") > role.count(")"):
        role = role + ")"
    elif role.count(")") > role.count("("):
        role = role.replace(")", "")
        
    # If role ends up being just noise, discard
    if len(role) < 2 or len(role) > 75:
        return ""
    # Title-case if appropriate or keep it as is
    if role.isupper() or role.islower():
        role = role.title()
    return role


def is_valid_role(role: str) -> bool:
    if not role:
        return False
    role_lower = role.lower()
    
    # 1. Reject if too short or too long
    if len(role) < 3 or len(role) > 75:
        return False
        
    # 2. Reject if starts with prepositions or common action verbs
    invalid_start_words = {
        "using", "with", "by", "on", "for", "at", "to", "in", "and", "from",
        "worked", "developed", "built", "created", "implemented", "managed", "designed",
        "assisted", "integrated", "collaborated", "led", "spearheaded", "optimized",
        "oversaw", "conducted", "participated", "gained", "improving", "enhancing", "securing"
    }
    words = role_lower.split()
    if words and words[0] in invalid_start_words:
        return False
        
    # 3. Reject if contains any education/degree keywords
    education_blacklist = {
        "bachelor", "master", "university", "college", "school", "institute", 
        "institude", "academy", "education", "hsc", "ssc", "degree", "diploma", 
        "cgpa", "grade", "percentage", "gpa", "marks", "board", "scool", "collage", 
        "inst.", "univ.", "student", "pursuing"
    }
    if any(w in education_blacklist for w in words):
        return False
        
    # 4. Reject if contains other typical description verbs
    description_verbs = {
        "used", "developed", "built", "worked", "created", "implemented", 
        "managed", "designed", "assisted", "integrated", "collaborated", 
        "led", "spearheaded", "optimized", "oversaw", "conducted", 
        "participated", "gained", "improving", "enhancing", "securing"
    }
    if any(w in description_verbs for w in words):
        return False
        
    # 5. Reject if contains specific message/template-like strings
    reject_substrings = ["subject:", "offer letter", "reference", "declaration"]
    if any(sub in role_lower for sub in reject_substrings):
        return False
        
    # 6. Reject if contains only digits or special characters
    if not any(c.isalpha() for c in role):
        return False
        
    return True


def extract_job_role(text: str, filename_name: str, candidate_name: str, model) -> str:
    # 1. Try to parse from the first 5-6 lines of the text
    lines = [line.strip() for line in text.splitlines() if line.strip()][:8]
    text_role = ""
    for line in lines:
        if "@" in line or "http" in line or ".com" in line or any(c.isdigit() for c in line if c not in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "+", "-", "(", ")", " "]):
            continue
            
        line_lower = line.lower()
        if candidate_name and candidate_name.lower() in line_lower:
            name_idx = line_lower.find(candidate_name.lower())
            before = line[:name_idx].strip()
            after = line[name_idx + len(candidate_name):].strip()
            
            for part in [after, before]:
                part_clean = clean_role(part)
                if part_clean and is_valid_role(part_clean) and any(kw in part_clean.lower() for kw in JOB_KEYWORDS):
                    text_role = part_clean
                    break
            if text_role:
                break
            continue
            
        if any(kw in line_lower for kw in JOB_KEYWORDS) and len(line) <= 75:
            if any(h in line_lower for h in ["experience", "education", "skills", "projects", "certifications", "summary"]):
                continue
            part_clean = clean_role(line)
            if is_valid_role(part_clean):
                text_role = part_clean
                break

    # 2. Try GLiNER on first 500 characters
    gliner_role = ""
    if model and text and not text_role:
        header_text = text[:500]
        header_text = re.sub(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', ' ', header_text)
        header_text = re.sub(r'(?<![\w@])(?:\+?\d[\d \t\-\.\(\)]{6,14}\d)(?![\w@])', ' ', header_text)
        
        entities = model.predict_entities(header_text, labels=["job title", "role", "position"], threshold=0.3)
        valid_roles = []
        for ent in sorted(entities, key=lambda x: x.get('score', 0), reverse=True):
            ent_text = clean_role(ent.get("text", ""))
            ent_lower = ent_text.lower()
            if ent_text and is_valid_role(ent_text) and any(kw in ent_lower for kw in JOB_KEYWORDS):
                if candidate_name and candidate_name.lower() in ent_lower:
                    ent_text = clean_role(ent_text.replace(candidate_name, "").replace(candidate_name.upper(), "").replace(candidate_name.title(), ""))
                if ent_text and is_valid_role(ent_text) and len(ent_text) <= 75:
                    valid_roles.append(ent_text)
                    break
        if valid_roles:
            gliner_role = valid_roles[0]

    # 3. Look in the filename itself
    filename_role = ""
    if not text_role and not gliner_role:
        stem = Path(filename_name).stem
        stem = re.sub(r'^\d+[-_]?', '', stem)
        stem = re.sub(r'([a-z])([A-Z])', r'\1 \2', stem)
        parts = re.split(r'[-_\s]+', stem)
        
        candidate_name_words = set(candidate_name.lower().split()) if candidate_name else set()
        role_parts_filename = []
        found_keyword = False
        for p in parts:
            p_clean = p.strip(".,;:()").lower()
            if not p_clean:
                continue
            if p_clean in candidate_name_words:
                continue
            if p_clean in ["resume", "cv", "updated", "final", "new", "placement", "copy"]:
                continue
            if any(kw in p_clean for kw in FILENAME_KEYWORDS):
                found_keyword = True
            role_parts_filename.append(p)
        
        if found_keyword and role_parts_filename:
            candidate_role = clean_role(" ".join(role_parts_filename))
            if is_valid_role(candidate_role):
                filename_role = candidate_role

    final_role = ""
    if text_role:
        final_role = text_role
    elif gliner_role:
        final_role = gliner_role
    elif filename_role:
        final_role = filename_role
        
    return final_role


def extract_basic_infos(text: str, model, original_name: str, threshold: float = 0.4) -> dict:
    """Extracts candidate full_name, job_role, location, email, phone, linkedin, and github from text."""
    # 1. Extract contact details
    contact_info = extract_email_phone(text)
    
    # 2. Extract social links
    social_info = extract_social_links(text)
    
    # 3. Extract name
    extracted_name = ""
    if text:
        text_chunk = text[:1000]
        entities = model.predict_entities(text_chunk, labels=["person"], threshold=threshold)
        
        valid_names = []
        for ent in entities:
            ent_text = clean_extracted_name(ent.get("text", ""))
            if is_valid_person_name(ent_text):
                valid_names.append((ent.get("start", 0), ent_text))
        
        if valid_names:
            valid_names.sort(key=lambda x: x[0])
            extracted_name = valid_names[0][1]

    if not extracted_name:
        extracted_name = extract_name_from_filename(original_name)

    # 4. Extract job role
    extracted_role = ""
    if text:
        extracted_role = extract_job_role(text, original_name, extracted_name, model)

    # 5. Extract location
    extracted_location = ""
    if text:
        extracted_location = extract_location(text, model, extracted_name, threshold=threshold)

    return {
        "full_name": extracted_name,
        "job_role": extracted_role,
        "location": extracted_location,
        "email": contact_info["email"],
        "phone": contact_info["phone"],
        "linkedin": social_info["linkedin"],
        "github": social_info["github"]
    }
