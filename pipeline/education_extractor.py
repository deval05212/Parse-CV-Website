import re

# Case-insensitive degree names
DEGREE_INSENSITIVE_RE = re.compile(
    r'\b(?:'
    r'b\.?tech\b|bca\b|mca\b|m\.?tech\b|mba\b|'
    r'b\.?sc\b|m\.?sc\b|b\.?com\b|m\.?com\b|ph\.?d\b|bba\b|'
    r'h\.?s\.?c\b|s\.?s\.?c\b|10th\b|12th\b|cbse\b|gseb\b|icse\b|ib\b|diploma\b|'
    r'bachelors?\s+(?:of|in)\s+[a-zA-Z0-9 \t]{2,50}\b|'
    r'masters?\s+(?:of|in)\s+[a-zA-Z0-9 \t]{2,50}\b|'
    r'bachelors?\b|masters?\b|'
    r'bachelor\s+of\s+engineering\b|bachelor\s+of\s+technology\b|'
    r'bachelor\s+of\s+computer\s+applications?\b|master\s+of\s+computer\s+applications?\b|'
    r'bachelor\s+of\s+science\b|master\s+of\s+science\b|'
    r'bachelor\s+of\s+commerce\b|master\s+of\s+commerce\b|'
    r'master\s+of\s+business\s+administration\b'
    r')\b',
    re.IGNORECASE
)

# Case-sensitive degree names to avoid common lowercase words like "be", "me" matching
# Allow optional trailing dot in B.E. and M.E.
DEGREE_SENSITIVE_RE = re.compile(
    r'\b(?:BE|B\.E\.?|ME|M\.E\.?)\b(?!\-)'
)

# Regex to detect universities and schools (excludes newlines inside the name match)
UNIVERSITY_SCHOOL_RE = re.compile(
    r'\b[A-Z][a-zA-Z0-9 \t\-\(\)\.,&\x27\u2019]{2,80}?\s*(?:'
    r'University|College|School|Institute|Institude|Academy|Vidyalaya|Vidhyalay|Sankul'
    r')(?:\s+(?:of|in|for|and)\s+[A-Z][a-zA-Z0-9 \t\-\(\)\.,&\x27\u2019]{1,60})?\b',
    re.IGNORECASE
)

# Regex for well-known university and college abbreviations (case-sensitive)
UNIVERSITY_ABBREVIATIONS_RE = re.compile(
    r'\b(?:IIT|NIT|IIIT|BITS|MIT|VNSGU|GTU|MSU|DAIICT|PDPU|PDEU|PTU|DTU|NSUT|PEC)\b'
)

# Blacklist of invalid degree words (cities, grade metrics, job terms)
BLACKLIST_DEGREES = {
    "cgpa", "sgpa", "gpa", "grade", "percentage", "marks", "marks:", "year",
    "surat", "ahmedabad", "vadodara", "baroda", "mumbai", "pune", "anand", "rajkot", "gujarat", "india",
    "project", "work", "experience", "internship", "intern", "developer", "engineer", "leader",
    "limited", "private", "pvt", "ltd", "corporation", "corp", "co", "company"
}


def exclude_experience_section(text: str) -> str:
    """Locates the experience section and removes it from the text, returning the rest.
    
    Smart multi-column detection: In many PDFs, EDUCATION and EXPERIENCE headers appear
    on consecutive lines (same multi-column header row). If EXPERIENCE is found within
    200 characters of an EDUCATION header, we treat it as a layout artifact and skip it,
    trying the next standalone EXPERIENCE occurrence instead.
    """
    exp_headers = [
        "experience", "work experience", "professional experience", "employment",
        "history", "work history", "professional background", "employment history"
    ]
    edu_headers = ["education", "academic", "schooling", "qualification", "studies", "credentials"]
    text_lower = text.lower()

    # Find all EDUCATION header positions
    edu_positions = set()
    for h in edu_headers:
        pattern = rf"(?im)^\s*[-•⚫■★*]*\s*\b{h}\b"
        for m in re.finditer(pattern, text_lower):
            edu_positions.add(m.start())

    # Find first EXPERIENCE header that is NOT adjacent to an EDUCATION header
    start_idx = -1
    for h in exp_headers:
        pattern = rf"(?im)^\s*[-•⚫■★*]*\s*\b{h}\b"
        matches = list(re.finditer(pattern, text_lower))
        for m in matches:
            # Check if this EXPERIENCE occurrence is within 200 chars of any EDUCATION header
            is_adjacent_to_education = any(abs(m.start() - edu_pos) <= 200 for edu_pos in edu_positions)
            if not is_adjacent_to_education:
                start_idx = m.start()
                break
        if start_idx != -1:
            break

    if start_idx == -1:
        return text

    # Find the next section header after the experience header to mark its end
    next_headers = [
        "education", "academic", "schooling", "qualification", "studies", "credentials",
        "project", "skill", "certificate", "interest", "language", "achievement", "declaration", "summary"
    ]

    remaining_text = text[start_idx:]
    remaining_text_lower = remaining_text.lower()

    end_idx = len(text)
    for nh in next_headers:
        pattern = rf"(?im)^\s*[-•⚫■★*]*\s*\b{nh}\b"
        matches = list(re.finditer(pattern, remaining_text_lower))
        for m in matches:
            # Ensure it is not the start (must be on a new line after the experience header)
            if "\n" in remaining_text_lower[:m.start()]:
                potential_end = start_idx + m.start()
                if potential_end < end_idx:
                    end_idx = potential_end
                break

    return text[:start_idx] + "\n" + text[end_idx:]


def extract_edu_section(text: str) -> tuple[str, int]:
    """Finds the education section in a resume text and returns (section_text, start_offset)."""
    headers = [
        "education", "academic", "schooling", "qualification", "studies", "credentials"
    ]
    
    text_lower = text.lower()
    start_idx = -1
    for header in headers:
        # Enforce that the header must be at the start of a line
        pattern = rf"(?im)^\s*[-•⚫■★*]*\s*\b{header}\b"
        matches = list(re.finditer(pattern, text_lower))
        if matches:
            start_idx = matches[0].start()
            break
            
    if start_idx == -1:
        return "", 0
        
    next_headers = [
        "experience", "project", "skill", "certificate", "interest", "language", "achievement", "declaration", "summary"
    ]
    
    remaining_text = text[start_idx:]
    remaining_text_lower = remaining_text.lower()
    
    end_idx = len(remaining_text)
    for next_header in next_headers:
        # Enforce start-of-line constraint
        pattern = rf"(?im)^\s*[-•⚫■★*]*\s*\b{next_header}\b"
        matches = list(re.finditer(pattern, remaining_text_lower))
        for m in matches:
            # Ensure it is not the start (must be on a new line after the education header)
            if "\n" in remaining_text_lower[:m.start()]:
                if m.start() < end_idx:
                    end_idx = m.start()
                break
                
    return remaining_text[:end_idx].strip(), start_idx


def balance_parentheses(text: str) -> str:
    """Balances unmatched parentheses in university/school names."""
    open_count = text.count('(')
    close_count = text.count(')')
    if open_count > close_count:
        text += ')' * (open_count - close_count)
    elif close_count > open_count:
        text = text.rstrip(')')
    return text


def clean_entity_text(text: str) -> str:
    """Cleans up extra spaces and punctuation from entities."""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
    text = balance_parentheses(text)
    return text


def is_valid_degree(text: str) -> bool:
    """Ensures a degree entity does not accidentally contain school keywords or noise."""
    text_clean = text.lower().strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
    if text_clean in BLACKLIST_DEGREES:
        return False
        
    # Check if it contains school/university keywords
    school_keywords = ["university", "college", "school", "institute", "institude", "academy", "sankul", "vidhyalay", "vidyabhavan"]
    if any(k in text_clean for k in school_keywords):
        return False
        
    # Reject pure numeric/symbols strings (e.g. grades or years)
    if re.match(r'^[\d\.\s%/\-\(\)]+$', text_clean):
        return False
        
    return True


def is_valid_school_name(school: str) -> bool:
    """Checks if a school/university entity candidate contains stop words or is blacklisted."""
    school_lower = school.lower().strip()
    if not school_lower:
        return False
        
    # Check for verbs, descriptions, and non-school activity terms
    invalid_keywords = [
        "received", "scholarship", "heading", "development", "develop", "built", "build",
        "managed", "led", "assisted", "participated", "won", "worked", "created",
        "designed", "implemented", "responsible", "responsibility", "duties", "roles",
        "menu", "order", "orders", "app", "apps", "application", "applications",
        "system", "systems", "platform", "platforms", "database", "framework", "using",
        "skills", "experience", "activities", "extra-curricular", "interest", "interests",
        "description", "details", "achievements", "achievement", "award", "awards"
    ]
    if any(w in school_lower for w in invalid_keywords):
        return False
        
    school_stop_words = ["training", "project", "olympiad", "olympaid", "placement", "workshop", "internship", "position", "rank", "winner"]
    if any(w in school_lower for w in school_stop_words):
        return False
        
    # Check bootcamp/platform keywords
    bootcamp_keywords = [
        "cipher", "sheryians", "coursera", "udemy", "toastmasters", 
        "linkedin", "microsoft", "google", "aws", "fdd", "gujcost", "gyanutsav"
    ]
    if any(w in school_lower for w in bootcamp_keywords):
        return False
        
    # Enforce school keywords or recognized abbreviations
    school_keywords = [
        "university", "college", "school", "institute", "institude", "academy", 
        "vidyalaya", "vidhyalay", "sankul", "board", "high", "sec", "secondary", 
        "center", "centre", "education", "technical", "polytechnic", "univ", "inst", "dept", "department"
    ]
    has_keyword = any(k in school_lower for k in school_keywords)
    is_abbreviation = bool(UNIVERSITY_ABBREVIATIONS_RE.search(school))
    
    if not (has_keyword or is_abbreviation):
        return False
        
    return True


def is_synonym(d1: str, d2: str) -> bool:
    """Checks if two degrees are synonyms/abbreviations of each other."""
    d1_clean = re.sub(r'[^a-zA-Z0-9]', '', d1).lower()
    d2_clean = re.sub(r'[^a-zA-Z0-9]', '', d2).lower()
    
    if not d1_clean or not d2_clean:
        return False
        
    # Normalize by stripping trailing 's' to handle plural differences (e.g. applications vs application)
    if d1_clean.endswith('s'):
        d1_clean = d1_clean[:-1]
    if d2_clean.endswith('s'):
        d2_clean = d2_clean[:-1]
        
    # Check abbreviations
    syn_map = {
        "btech": "bacheloroftechnology",
        "be": "bachelorofengineering",
        "mtech": "masteroftechnology",
        "me": "masterofengineering",
        "bca": "bachelorofcomputerapplication",
        "mca": "masterofcomputerapplication",
        "bcom": "bachelorofcommerce",
        "mcom": "masterofcommerce",
        "bsc": "bachelorofscience",
        "msc": "masterofscience",
        "mba": "masterofbusinessadministration",
        "bba": "bachelorofbusinessadministration",
        "hsc": "highersecondary",
        "ssc": "secondaryschool"
    }
    
    for k, v in syn_map.items():
        if (d1_clean == k and d2_clean == v) or (d2_clean == k and d1_clean == v):
            return True
            
    if d1_clean in d2_clean or d2_clean in d1_clean:
        return True
        
    return False


def split_mixed_degree_string(text: str) -> list[str]:
    """Splits a degree string into multiple degrees if it contains multiple known degrees."""
    text = clean_entity_text(text)
    matches = []
    for m in DEGREE_INSENSITIVE_RE.finditer(text):
        matches.append((m.start(), m.end(), m.group(0)))
    for m in DEGREE_SENSITIVE_RE.finditer(text):
        matches.append((m.start(), m.end(), m.group(0)))
        
    # Resolve overlapping matches (keep the longest match)
    matches = sorted(matches, key=lambda x: (x[1] - x[0]), reverse=True)
    non_overlapping_matches = []
    for m in matches:
        m_start, m_end, m_text = m
        overlap = False
        for nom in non_overlapping_matches:
            nom_start, nom_end, _ = nom
            if not (m_end <= nom_start or m_start >= nom_end):
                overlap = True
                break
        if not overlap:
            non_overlapping_matches.append(m)
            
    non_overlapping_matches = sorted(non_overlapping_matches, key=lambda x: x[0])
    
    if len(non_overlapping_matches) < 2:
        return [text]
        
    # Split on +, /, comma, and parentheses
    parts = re.split(r'\s*(?:\+|/|,|\(|\))\s*', text)
    
    result = []
    for part in parts:
        cleaned = clean_entity_text(part)
        if cleaned:
            part_has_degree = False
            for m in non_overlapping_matches:
                _, _, m_text = m
                if m_text.lower() in cleaned.lower() or is_synonym(m_text, cleaned):
                    part_has_degree = True
                    break
            if part_has_degree:
                result.append(cleaned)
            else:
                if result:
                    result[-1] = f"{result[-1]}, {cleaned}"
                else:
                    result.append(cleaned)
    return result


def normalize_degree_name(deg: str) -> str:
    """Normalizes degree names to a canonical representation."""
    cleaned = deg.strip()
    if not cleaned:
        return ""
        
    # Strip trailing sections/noise headers like certifications, projects, etc.
    cleaned = re.sub(r'(?i)\s*[-:|/()\[\]]*\s*\b(?:certifications?|projects?|skills?|experience|achievements?|activities|interests?)\b.*', '', cleaned)
    cleaned = cleaned.strip()
    
    cleaned_lower = cleaned.lower()
    
    # Replacement rules matching abbreviation patterns to their canonical names
    replacement_rules = [
        (re.compile(r'\b(?:m\.?sc\.?\s*(?:in\s+)?it|msc\s*it|masters?\s+of\s+science\s+in\s+(?:it|information\s+technology))\b', re.I), "Master of Science in Information Technology"),
        (re.compile(r'\b(?:bca|b\.c\.a\.?|bachelors?\s+of\s+computer\s+applications?)\b', re.I), "Bachelor of Computer Applications"),
        (re.compile(r'\b(?:mca|m\.c\.a\.?|masters?\s+of\s+computer\s+applications?)\b', re.I), "Master of Computer Applications"),
        (re.compile(r'\b(?:b\.?tech|bachelors?\s+of\s+technology)\b', re.I), "Bachelor of Technology"),
        (re.compile(r'\b(?:m\.?tech|masters?\s+of\s+technology)\b', re.I), "Master of Technology"),
        (re.compile(r'\b(?:b\.?sc|bachelors?\s+of\s+science)\b', re.I), "Bachelor of Science"),
        (re.compile(r'\b(?:m\.?sc|masters?\s+of\s+science)\b', re.I), "Master of Science"),
        (re.compile(r'\b(?:b\.?com|bachelors?\s+of\s+commerce)\b', re.I), "Bachelor of Commerce"),
        (re.compile(r'\b(?:m\.?com|masters?\s+of\s+commerce)\b', re.I), "Master of Commerce"),
        (re.compile(r'\b(?:mba|masters?\s+of\s+business\s+administration)\b', re.I), "Master of Business Administration"),
        (re.compile(r'\b(?:bba|bachelors?\s+of\s+business\s+administration)\b', re.I), "Bachelor of Business Administration"),
        (re.compile(r'\b(?:be|b\.e\.?|bachelors?\s+of\s+engineering)\b', re.I), "Bachelor of Engineering"),
        (re.compile(r'\b(?:me|m\.e\.?|masters?\s+of\s+engineering)\b', re.I), "Master of Engineering"),
        (re.compile(r'\b(?:h\.?s\.?c|12th|cbse\s*12th|gseb\s*12th|higher\s+secondary\s*certificate|higher\s+secondary)\b', re.I), "Higher Secondary Certificate"),
        (re.compile(r'\b(?:s\.?s\.?c|10th|cbse\s*10th|gseb\s*10th|secondary\s*school\s*certificate|secondary\s*school)\b', re.I), "Secondary School Certificate"),
    ]
    
    for pattern, canonical in replacement_rules:
        if pattern.search(cleaned_lower):
            substituted = pattern.sub(canonical, cleaned)
            return re.sub(r'\s+', ' ', substituted).strip()
            
    return cleaned


def is_valid_education_record(item: dict) -> bool:
    """Filters out low-confidence/partial extractions where one of the fields is empty
    and cannot be reasonably validated or inferred.
    """
    deg = item.get("degree_or_board", "").strip()
    school = item.get("university_or_school", "").strip()
    
    # 1. If both are empty, reject
    if not deg and not school:
        return False
        
    # 2. If degree is empty but school is not, check if it looks like a high-confidence educational institution
    if not deg and school:
        school_lower = school.lower()
        
        # High-confidence educational keywords (excluding bootcamps and platforms)
        high_conf_keywords = ["university", "college", "institute", "institude"]
        
        # Blacklisted platforms/courses that often appear as school names
        bootcamp_keywords = [
            "cipher", "sheryians", "coursera", "udemy", "toastmasters", 
            "linkedin", "microsoft", "google", "aws", "fdd", "gujcost", "gyanutsav"
        ]
        
        # Check if the school name contains high-confidence keywords
        has_high_conf = any(k in school_lower for k in high_conf_keywords)
        has_blacklist = any(k in school_lower for k in bootcamp_keywords)
        
        # Discard generic names alone
        is_generic = school_lower in ["university", "college", "school", "institute", "institude", "vidyalaya", "academy"]
        
        if not has_high_conf or has_blacklist or is_generic:
            return False
            
    # 3. If school is empty but degree is not, check if it contains a known degree or board keyword
    if not school and deg:
        has_known_degree = bool(DEGREE_INSENSITIVE_RE.search(deg) or DEGREE_SENSITIVE_RE.search(deg))
        extra_degree_keywords = [
            "bachelor", "master", "doctor", "phd", "diploma", "degree", 
            "hsc", "ssc", "h.s.c", "s.s.c", "board", "cbse", "gseb", "icse", 
            "intermediate", "matric", "matriculation", "10th", "12th"
        ]
        deg_lower = deg.lower()
        has_extra_deg = any(k in deg_lower for k in extra_degree_keywords)
        
        # Discard job boards, job titles, or platforms
        blacklist_degree_words = [
            "jobdiva", "monster", "dice", "techfetch", "linkedin", "spi-", 
            "nypa", "nycha", "pdeu"
        ]
        has_blacklist_word = any(k in deg_lower for k in blacklist_degree_words)
        
        if not (has_known_degree or has_extra_deg) or has_blacklist_word:
            return False
            
    # 4. Filter out experience/achievement stop words
    deg_lower = deg.lower()
    school_lower = school.lower()
    has_known_degree = bool(DEGREE_INSENSITIVE_RE.search(deg) or DEGREE_SENSITIVE_RE.search(deg))
    
    # Strong experience/activity stop words (discard immediately)
    strong_experience_words = ["worked", "participated", "volunteer", "achievement", "represent"]
    if any(re.search(rf"\b{w}", deg_lower) or re.search(rf"\b{w}", school_lower) for w in strong_experience_words):
        return False
        
    # Standard stop words (discard if no known degree is present)
    if not has_known_degree:
        if any(re.search(rf"\b{w}", deg_lower) or re.search(rf"\b{w}", school_lower) for w in ["project", "internship"]):
            return False
            
    # School stop words (discard if school name matches non-school/activity keywords)
    school_stop_words = ["training", "project", "olympiad", "olympaid", "placement", "workshop", "internship", "position", "rank", "winner"]
    if any(w in school_lower for w in school_stop_words):
        return False
            
    return True


def group_entities_refined(entities, section_text):
    """Refined grouping using state machine based on lines and entity types."""
    # 1. Clean and filter initial entities
    cleaned_entities = []
    for ent in entities:
        text_clean = clean_entity_text(ent['text'])
        if not text_clean:
            continue
        # Validate school name
        if ent['label'] in ['school', 'university', 'university_or_school']:
            if not is_valid_school_name(text_clean):
                continue
        cleaned_entities.append({
            'start': ent['start'],
            'end': ent['end'],
            'label': ent['label'],
            'text': text_clean
        })
        
    # 2. Add regex-based degrees/boards if they don't overlap with existing entities of same type
    # A. Case-insensitive degree regex
    for m in DEGREE_INSENSITIVE_RE.finditer(section_text):
        m_start = m.start()
        m_end = m.end()
        m_text = m.group(0)
        
        overlap = False
        for ent in cleaned_entities:
            if ent['label'] in ['degree', 'board']:
                if not (m_end <= ent['start'] or m_start >= ent['end']):
                    overlap = True
                    break
                
        if not overlap:
            cleaned_entities.append({
                'start': m_start,
                'end': m_end,
                'label': 'degree',
                'text': clean_entity_text(m_text)
            })
            
    # B. Case-sensitive degree regex
    for m in DEGREE_SENSITIVE_RE.finditer(section_text):
        m_start = m.start()
        m_end = m.end()
        m_text = m.group(0)
        
        overlap = False
        for ent in cleaned_entities:
            if ent['label'] in ['degree', 'board']:
                if not (m_end <= ent['start'] or m_start >= ent['end']):
                    overlap = True
                    break
                
        if not overlap:
            cleaned_entities.append({
                'start': m_start,
                'end': m_end,
                'label': 'degree',
                'text': clean_entity_text(m_text)
            })
            
    # C. University/School regex
    for m in UNIVERSITY_SCHOOL_RE.finditer(section_text):
        m_start = m.start()
        m_end = m.end()
        m_text = m.group(0)
        
        if not is_valid_school_name(m_text):
            continue
            
        overlap = False
        for ent in cleaned_entities:
            if ent['label'] in ['university', 'school']:
                if not (m_end <= ent['start'] or m_start >= ent['end']):
                    overlap = True
                    break
                
        if not overlap:
            cleaned_entities.append({
                'start': m_start,
                'end': m_end,
                'label': 'university',
                'text': clean_entity_text(m_text)
            })
            
    # D. University Abbreviations regex
    for m in UNIVERSITY_ABBREVIATIONS_RE.finditer(section_text):
        m_start = m.start()
        m_end = m.end()
        m_text = m.group(0)
        
        if not is_valid_school_name(m_text):
            continue
            
        overlap = False
        for ent in cleaned_entities:
            if ent['label'] in ['university', 'school']:
                if not (m_end <= ent['start'] or m_start >= ent['end']):
                    overlap = True
                    break
                
        if not overlap:
            cleaned_entities.append({
                'start': m_start,
                'end': m_end,
                'label': 'university',
                'text': clean_entity_text(m_text)
            })
            
    # 3. Resolve overlaps and prioritize degrees
    def get_priority(ent):
        return 0 if ent['label'] in ['degree', 'board'] else 1
        
    sorted_ents = sorted(cleaned_entities, key=lambda x: (get_priority(x), x['start']))
    
    non_overlapping = []
    
    for ent in sorted_ents:
        if ent['label'] in ['degree', 'board']:
            # Ensure it is a valid degree name and not a school name or city/noise term
            if not is_valid_degree(ent['text']):
                continue
                
            overlap = False
            for existing in non_overlapping:
                if existing['label'] in ['degree', 'board']:
                    if not (ent['end'] <= existing['start'] or ent['start'] >= existing['end']):
                        overlap = True
                        if (ent['end'] - ent['start']) > (existing['end'] - existing['start']):
                            non_overlapping.remove(existing)
                            non_overlapping.append(ent)
                        break
            if not overlap:
                non_overlapping.append(ent)
        else:
            current_start = ent['start']
            current_end = ent['end']
            
            discard = False
            for existing in non_overlapping:
                if existing['label'] in ['degree', 'board']:
                    if not (current_end <= existing['start'] or current_start >= existing['end']):
                        if existing['start'] <= current_start < existing['end']:
                            current_start = existing['end']
                        elif existing['start'] < current_end <= existing['end']:
                            current_end = existing['start']
                        else:
                            discard = True
                            break
                            
            if not discard and current_start < current_end:
                adjusted_text = clean_entity_text(section_text[current_start:current_end])
                if adjusted_text and len(adjusted_text) >= 3:
                    ent['start'] = current_start
                    ent['end'] = current_end
                    ent['text'] = adjusted_text
                    non_overlapping.append(ent)
                    
    # Re-sort final list by start index
    non_overlapping = sorted(non_overlapping, key=lambda x: x['start'])
    
    # Assign line numbers
    for ent in non_overlapping:
        preceding_text = section_text[:ent['start']]
        ent['line'] = preceding_text.count('\n')
        
    # Separate degrees and schools
    degrees_list = [ent for ent in non_overlapping if ent['label'] in ['degree', 'board']]
    schools_list = [ent for ent in non_overlapping if ent['label'] in ['school', 'university']]
    
    # Pre-clean all degrees
    cleaned_degrees = []
    for d in degrees_list:
        split_degs = split_mixed_degree_string(d['text'])
        for sd in split_degs:
            cleaned_degrees.append({
                'text': sd,
                'line': d['line'],
                'start': d['start']
            })
            
    # Pre-clean all schools
    cleaned_schools = []
    for s in schools_list:
        cleaned_uni = balance_parentheses(s['text'])
        if cleaned_uni:
            cleaned_schools.append({
                'text': cleaned_uni,
                'line': s['line'],
                'start': s['start']
            })
            
    entries = []
    
    # Check if we have a parallel layout
    is_parallel = False
    if cleaned_schools and cleaned_degrees:
        last_school_end = max(s['start'] for s in cleaned_schools)
        first_degree_start = min(d['start'] for d in cleaned_degrees)
        last_degree_end = max(d['start'] for d in cleaned_degrees)
        first_school_start = min(s['start'] for s in cleaned_schools)
        
        if last_school_end <= first_degree_start or last_degree_end <= first_school_start:
            is_parallel = True
            
    if is_parallel:
        # Pair 1-to-1 by index
        for i, deg_ent in enumerate(cleaned_degrees):
            deg_text = deg_ent['text']
            if i < len(cleaned_schools):
                school_text = cleaned_schools[i]['text']
            else:
                school_text = ""
            entries.append({
                "degree_or_board": deg_text,
                "university_or_school": school_text
            })
    else:
        # Group degrees by line number
        degrees_by_line = {}
        for d in cleaned_degrees:
            degrees_by_line.setdefault(d['line'], []).append(d)
            
        available_schools = list(cleaned_schools)
        line_school_map = {}
        
        # Pass 1: Same line schools for each line with degrees
        for line in list(degrees_by_line.keys()):
            same_line_schools = [s for s in available_schools if s['line'] == line]
            if same_line_schools:
                school_str = ", ".join(s['text'] for s in same_line_schools)
                line_school_map[line] = school_str
                for s in same_line_schools:
                    if s in available_schools:
                        available_schools.remove(s)
                        
        # Pass 2: Nearest school for each line with degrees (within 2 lines threshold)
        for line in sorted(degrees_by_line.keys()):
            if line not in line_school_map:
                if available_schools:
                    closest_school = min(
                        available_schools,
                        key=lambda s: (abs(s['line'] - line), 0 if (s['line'] <= line) else 1)
                    )
                    if abs(closest_school['line'] - line) <= 2:
                        line_school_map[line] = closest_school['text']
                        available_schools.remove(closest_school)
                    else:
                        line_school_map[line] = ""
                else:
                    line_school_map[line] = ""
                    
        # Construct entries
        for line, degs in degrees_by_line.items():
            school_str = line_school_map.get(line, "")
            for d in degs:
                entries.append({
                    "degree_or_board": d['text'],
                    "university_or_school": school_str
                })
                
        if cleaned_schools and not cleaned_degrees:
            school_str = ", ".join(s['text'] for s in cleaned_schools)
            entries.append({
                "degree_or_board": "",
                "university_or_school": school_str
            })
            
    # Global deduplication, normalization, and school merging layer
    deg_to_schools = {}
    deg_order = []
    
    for entry in entries:
        if not is_valid_education_record(entry):
            continue
            
        deg = entry.get("degree_or_board", "")
        school = entry.get("university_or_school", "").strip()
        
        # Apply normalization layer
        norm_deg = normalize_degree_name(deg)
        
        if norm_deg not in deg_to_schools:
            deg_to_schools[norm_deg] = []
            deg_order.append(norm_deg)
            
        if school:
            norm_school = re.sub(r'[^a-z0-9]', '', school.lower())
            school_exists = False
            for existing_school in deg_to_schools[norm_deg]:
                existing_norm = re.sub(r'[^a-z0-9]', '', existing_school.lower())
                if existing_norm == norm_school:
                    school_exists = True
                    break
            if not school_exists:
                deg_to_schools[norm_deg].append(school)
                
    final_entries = []
    for norm_deg in deg_order:
        schools = deg_to_schools[norm_deg]
        school_str = ", ".join(schools) if schools else ""
        final_entries.append({
            "degree_or_board": norm_deg,
            "university_or_school": school_str
        })
        
    return final_entries


def classify_education_item(item: dict) -> str:
    """Classifies an extracted education item into education, certification, or project."""
    deg = item.get("degree_or_board", "")
    school = item.get("university_or_school", "")
    
    # Check if it contains a known degree in the degree_or_board field
    has_known_degree = bool(DEGREE_INSENSITIVE_RE.search(deg) or DEGREE_SENSITIVE_RE.search(deg))
    
    # Define regex patterns for projects and certifications
    PROJECT_RE = re.compile(
        r'\b(?:project|built|developed|designed|created|implemented|system|platform)\b|\b(?<!computer\s)applications?\b',
        re.IGNORECASE
    )
    
    CERTIFICATION_RE = re.compile(
        r'\b(?:certified|certification|certificate|springboard|internship|workshop|training|course|bootcamp|credential)\b',
        re.IGNORECASE
    )
    
    ACADEMY_RE = re.compile(r'\bacadem(?:y|ies)\b', re.IGNORECASE)
    
    # Classification logic
    if has_known_degree:
        # If it has a known degree, it is education unless:
        # 1. The degree itself contains a project keyword
        if PROJECT_RE.search(deg):
            return "project"
        # 2. The degree itself contains a certification keyword
        if CERTIFICATION_RE.search(deg):
            return "certification"
        # Otherwise, it's education
        return "education"
    else:
        # No known degree
        # Check if it matches project keywords in either field
        if PROJECT_RE.search(deg) or PROJECT_RE.search(school):
            return "project"
        # Check if it matches certification keywords (including academy) in either field
        if (CERTIFICATION_RE.search(deg) or CERTIFICATION_RE.search(school) or 
            ACADEMY_RE.search(deg) or ACADEMY_RE.search(school)):
            return "certification"
        
        # Fallback: if there is no known degree and no keywords, default to education
        return "education"


def extract_education(text: str, model, threshold: float = 0.3) -> dict[str, list[dict]]:
    """Main entry point to extract education entries globally from raw resume text."""
    if not text:
        return {"education": []}
        
    # Exclude experience section from text to prevent false positive matches
    cleaned_text = exclude_experience_section(text)
    
    labels = ["degree", "university", "school", "board"]
    entities = model.predict_entities(cleaned_text, labels=labels, threshold=threshold)
    
    raw_entries = group_entities_refined(entities, cleaned_text)
    
    result = {
        "education": []
    }
    
    for entry in raw_entries:
        category = classify_education_item(entry)
        if category not in ["project", "certification"]:
            result["education"].append(entry)
            
    return result

