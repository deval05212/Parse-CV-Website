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


def extract_basic_infos(text: str, model, original_name: str, threshold: float = 0.4) -> dict:
    """Extracts candidate full_name, location, email, phone, linkedin, and github from text."""
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

    # 4. Extract location
    extracted_location = ""
    if text:
        extracted_location = extract_location(text, model, extracted_name, threshold=threshold)

    return {
        "full_name": extracted_name,
        "location": extracted_location,
        "email": contact_info["email"],
        "phone": contact_info["phone"],
        "linkedin": social_info["linkedin"],
        "github": social_info["github"]
    }
