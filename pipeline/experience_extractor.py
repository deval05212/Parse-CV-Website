import re
import logging
from typing import List, Dict, Any, Tuple, Optional

try:
    from pipeline.skills_extractor import TECH_KEYWORDS
except ImportError:
    TECH_KEYWORDS = set()

log = logging.getLogger(__name__)


class ExperienceExtractor:
    """
    Modular extractor for resume 'Experience' sections.
    Uses section segmentation followed by context-aware NER.
    """

    SECTION_HEADERS = [
        "experience", "work experience", "professional experience",
        "employment history", "work history", "professional background",
        "employment", "experience summary", "internship experience",
        "career history", "professional work experience"
    ]

    # Sections that typically follow Experience
    NEXT_SECTION_HEADERS = [
        "education", "skills", "technical skills", "projects",
        "certificates", "certifications", "languages", "interests",
        "achievements", "awards", "personal details", "references",
        "declaration", "hobbies", "training", "training and internships",
        "courses", "coursework", "academic projects", "portfolio",
        "professional experience and achievements", "additional experience and information"
    ]

    DATE_PART = (
        r'(?:'
        r'(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}'  # MM/YYYY or MM-YYYY
        r'|(?:19|20)\d{2}(?:[-/]\d{2})?'
        r'|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?:19|20)\d{2}'
        r')'
    )
    DATE_RE = re.compile(
        rf'\b({DATE_PART})\b(?:\s*(?:[-–—]|to|until)?\s*\b({DATE_PART}|present|current)\b)?',
        re.I,
    )
    ROLE_MARKERS = {
        "engineer", "developer", "manager", "lead", "senior", "executive",
        "intern", "associate", "analyst", "specialist", "coordinator",
        "officer", "recruiter", "consultant", "trainee", "admin", "assistant",
        "sales", "marketing", "hr", "software", "frontend", "backend",
        "full-stack", "mern-stack", "web", "business", "development",
        "account", "accounts", "designer", "scientist", "architect",
        "programmer", "tester", "qa", "representative", "director", "head",
        "expert", "consulting", "adviser", "advisor", "employee", "support",
        "technician", "leader", "leadership", "teacher", "lecturer", 
        "professor", "instructor", "tutor", "trainer", "teaching",
        "seo", "aso", "smm", "sem", "bde", "bca", "mca"
    }
    STRONG_ROLE_MARKERS = {
        "engineer", "developer", "manager", "lead", "senior", "executive",
        "intern", "associate", "analyst", "specialist", "coordinator",
        "officer", "recruiter", "consultant", "trainee", "admin", "assistant",
        "frontend", "backend", "full-stack", "mern-stack", "hr", "deputy",
        "designer", "scientist", "architect", "programmer", "tester", "qa",
        "representative", "director", "head", "expert", "support", "technician",
        "teacher", "lecturer", "professor", "instructor", "tutor", "trainer",
        "seo", "aso", "smm", "sem", "bde"
    }
    COMPANY_MARKERS = {
        "ltd", "limited", "inc", "corp", "corporation", "solutions", "solution", "services",
        "technologies", "technology", "global", "pvt", "llp", "llc", "systems",
        "bank", "consultancy", "group", "labs", "infotech", "soft", "software",
        "consulting", "agency", "industries", "industry", "institute", "academy",
        "university", "college", "school", "foundation", "ventures", "learning",
        "softech", "technolab", "infosoft"
    }
    STRONG_COMPANY_MARKERS = {
        "ltd", "limited", "inc", "corp", "corporation", "solutions", "solution", "services",
        "technologies", "technology", "pvt", "llp", "llc", "systems", "labs",
        "infotech", "consultancy", "ventures", "learning", "softech", "technolab", "infosoft"
    }
    DESCRIPTION_STARTERS = {
        "worked", "created", "implemented", "integrated", "gained", "learned",
        "understood", "managed", "led", "spearheaded", "developed", "designed",
        "built", "conducted", "driving", "coordinated", "maintained",
        "successfully", "training", "development", "optimization",
        "problem-solving", "technical expertise", "roles and responsibilities",
        "key achievements", "responsibilities", "closed", "secured", "expanded",
        "recognized"
    }

    def __init__(self, model):
        self.model = model
        self.labels = ["company", "job title", "date range", "location", "job description"]

    def extract(self, text: str, candidate_name: str = "") -> List[Dict[str, Any]]:
        """Main entry point to extract experience entries."""
        self.candidate_name = candidate_name
        self.full_text = text
        section_text = self._get_experience_section(text)
        if not section_text:
            log.warning("No experience section found.")
            return []

        log.debug(f"Extracted experience section ({len(section_text)} chars).")

        rule_entries = self._rule_based_fallback(section_text)
        
        entities = self._run_ner(section_text)
        if not entities:
            log.warning("GLiNER found no entities in the experience section.")
            recovered_rule = self._validate_and_recover_entries(rule_entries, section_text)
            filtered_rule = [job for job in recovered_rule if self._calculate_entry_confidence(job) >= 0.6]
            return filtered_rule

        ner_entries = self._group_entities(entities, section_text)
        
        recovered_rule = self._validate_and_recover_entries(rule_entries, section_text)
        recovered_ner = self._validate_and_recover_entries(ner_entries, section_text)
        
        filtered_rule = [job for job in recovered_rule if self._calculate_entry_confidence(job) >= 0.6]
        filtered_ner = [job for job in recovered_ner if self._calculate_entry_confidence(job) >= 0.6]
        
        if self._score_entries(filtered_rule) >= self._score_entries(filtered_ner):
            log.info("Using rule-based experience entries; they scored better than GLiNER grouping.")
            return filtered_rule

        return filtered_ner

    def _get_experience_section(self, text: str) -> str:
        """Robustly isolates the experience section."""
        lines = text.split("\n")
        start_idx = -1
        
        # Find start
        for i, line in enumerate(lines):
            clean_line = self._clean_section_name(line)
            if self._is_experience_header(clean_line):
                # Guard against sentence continuations:
                # 1. Headers never end with a period.
                if line.strip().endswith("."):
                    continue
                start_idx = i + 1
                break
        
        if start_idx == -1:
            # Try fuzzy/substring match for headers
            for i, line in enumerate(lines):
                clean_line = self._clean_section_name(line)
                if "rofessional experience" in clean_line and len(clean_line) < 40:
                    start_idx = i + 1
                    break
        
        if start_idx == -1:
            return ""

        # Find end
        end_idx = len(lines)
        for i in range(start_idx, len(lines)):
            clean_line = self._clean_section_name(lines[i])
            if self._is_next_section_header(clean_line):
                end_idx = i
                break

        return "\n".join(lines[start_idx:end_idx]).strip()

    def _clean_section_name(self, line: str) -> str:
        line = re.sub(r'^[\s•\-\*]+', '', line.strip().lower())
        line = re.sub(r'[:\-.]+$', '', line).strip()
        line = re.sub(r'\s+', ' ', line)
        return line

    def _is_experience_header(self, clean_line: str) -> bool:
        if clean_line in self.SECTION_HEADERS:
            return True
        if clean_line in {"work experience s", "professional experiences"}:
            return True
        
        # Check prefix match for common headers (handles trailing dates/locations)
        prefixes = [
            "work experience", "professional experience", "employment history", 
            "work history", "internship experience", "experience summary", "career history"
        ]
        if any(clean_line.startswith(p) for p in prefixes) and len(clean_line) < 45:
            return True
        if clean_line.startswith("experience") and len(clean_line) < 45:
            return True
            
        return bool(re.fullmatch(r'(?:work |professional |internship )?experience\s*\(?\d*(?:\.\d+)?\s*(?:yrs?\.?|years?)?\.?\)?', clean_line))

    def _is_next_section_header(self, clean_line: str) -> bool:
        if clean_line in self.NEXT_SECTION_HEADERS:
            return True
        if clean_line.endswith("s") and clean_line[:-1] in self.NEXT_SECTION_HEADERS:
            return True
        return bool(re.fullmatch(
            r'(?:projects?|skills?|education|certifications?|certificates?|languages?|training(?: and internships)?|awards?|achievements?|hobbies|references)',
            clean_line,
        ))

    def _run_ner(self, section_text: str) -> List[Dict[str, Any]]:
        """Runs GLiNER on the section text."""
        try:
            # Threshold set to 0.4 for higher recall in section-specific context
            entities = self.model.predict_entities(section_text, self.labels, threshold=0.4)
            # Sort by start position
            entities.sort(key=lambda x: x["start"])
            return entities
        except Exception as e:
            log.exception(f"NER failed on experience section: {e}")
            return []

    def _group_entities(self, entities: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """Groups flat entities into job entries using sequence logic."""
        jobs = []
        current_job = self._empty_job()
        
        def commit_job(job):
            if job["company"] or job["role"]:
                # 1. Clean swapped or merged roles first (splits, location, dates, swaps)
                self._clean_swapped_or_merged_roles(job, text)
                
                # 2. Company validation layer (on the cleaned company name)
                if job["company"] and not self._is_valid_company(job["company"], text):
                    log.info(f"Rejecting invalid company name: {job['company']}")
                    job["company"] = ""
                
                # Post-process duration and dates
                start, end, dur = self._parse_date_range(job["duration"])
                job["duration"] = dur
                job["start_date"] = self._normalize_to_yyyy_mm(start)
                job["end_date"] = self._normalize_to_yyyy_mm(end)
                
                # Clean up description
                job["description"] = self._clean_description(job["description"])
                
                if job["company"] or job["role"]:
                    jobs.append(job)
        
        for i, ent in enumerate(entities):
            label = ent["label"].replace(" ", "_")
            val = ent["text"].strip()
            start, end = ent["start"], ent["end"]
            
            # Map 'job_title' to 'role'
            field = "role" if label == "job_title" else label
            field = "duration" if label == "date_range" else field
            
            is_new_start = False
            
            # Logic for starting a new job entry
            if field == "duration" and current_job["duration"]:
                # If we see a new date range and we already have one, check if it's a continuation/end date
                prev_dur_ent = None
                for prev_ent in reversed(entities[:i]):
                    prev_label = prev_ent["label"].replace(" ", "_")
                    prev_field = "duration" if prev_label == "date_range" else prev_label
                    if prev_field == "duration":
                        prev_dur_ent = prev_ent
                        break
                
                is_continuation = False
                if prev_dur_ent:
                    between_text = text[prev_dur_ent["end"]:start].strip()
                    if len(between_text) < 30:
                        between_lower = between_text.lower()
                        # check if it contains any strong role or company markers
                        has_marker = any(m in between_lower for m in self.STRONG_ROLE_MARKERS | self.STRONG_COMPANY_MARKERS)
                        if not has_marker:
                            is_continuation = True
                
                if is_continuation:
                    # Merge them
                    sep = " - "
                    if between_text in {"-", "–", "—", "to", "until"}:
                        sep = f" {between_text} "
                    current_job["duration"] = f"{current_job['duration']}{sep}{val}"
                else:
                    is_new_start = True
            elif field in {"company", "role"} and current_job.get(field):
                # If we have both company and role, seeing another one starts a new job
                if current_job["company"] and current_job["role"]:
                    is_new_start = True
            
            if is_new_start:
                commit_job(current_job)
                current_job = self._empty_job()

            # Assign entity
            if field == "job_description":
                current_job["description"] = (current_job["description"] + " " + val).strip()
            elif field in current_job:
                if not current_job[field]:
                    current_job[field] = val
                elif field == "location":
                     current_job[field] += ", " + val
            
            # Gap filling: handle text between entities
            next_start = entities[i+1]["start"] if i+1 < len(entities) else len(text)
            gap_text = text[end:next_start].strip()
            
            if len(gap_text) > 3 and not re.match(r'^[|,\-\s•]+$', gap_text):
                # IMPROVED: Check if gap contains a date range
                date_match = re.search(r'(\d{4}[-/]\d{2}|\d{4}|[A-Z][a-z]{2,8}\s+\d{4})(?:\s*[-–—to]+\s*)?(\d{4}[-/]\d{2}|\d{4}|present|current)?', gap_text, re.I)
                
                if not current_job["duration"] and date_match:
                    # Extract only the date part for duration, rest goes to description
                    current_job["duration"] = date_match.group(0).strip()
                    remainder = (gap_text[:date_match.start()] + " " + gap_text[date_match.end():]).strip()
                    if len(remainder) > 3:
                        current_job["description"] = (current_job["description"] + " " + remainder).strip()
                else:
                    # No date match or already have duration, treat as description
                    current_job["description"] = (current_job["description"] + " " + gap_text).strip()

        commit_job(current_job)
        return jobs

    def _is_valid_company(self, company: str, text: str) -> bool:
        company_clean = company.strip(" ,.-–—|/()[]{}")
        if not company_clean:
            return False
            
        company_lower = company_clean.lower()
        words = company_lower.split()
        
        # 1. Blacklist check (early reject)
        INVALID_COMPANIES = {
            "experience",
            "summary",
            "profile",
            "objective",
            "certifications",
            "key highlights",
            "present",
            "portfolio",
            "achievements",
            "responsibilities",
            "highlight",
            "certification",
            "duration"
        }
        strong_suffixes = {"ltd", "limited", "inc", "corp", "corporation", "pvt", "llp", "llc", "gmbh", "co"}
        has_strong_suffix = any(w in strong_suffixes for w in words)
        
        if any(blacklisted == company_lower or (blacklisted in words and not has_strong_suffix) for blacklisted in INVALID_COMPANIES):
            return False

        # 2. Reject if word count > 7
        if len(words) > 7:
            return False

        # 3. Reject if contains many verbs
        if self._contains_many_verbs(company_lower):
            return False

        # 4. Reject if all lowercase sentence (no uppercase letters at all)
        if self._is_all_lowercase_sentence(company):
            return False
            
        # 5. Reject company if it ends with sentence-ending punctuation (excluding common abbreviations)
        company_trimmed = company.strip()
        if company_trimmed and company_trimmed[-1] in {".", "!", "?", ";"}:
            abbrev_words = {"ltd.", "pvt.", "co.", "inc.", "corp."}
            last_word = company_trimmed.split()[-1].lower() if company_trimmed.split() else ""
            if last_word not in abbrev_words:
                return False

        # 6. Reject company if it contains invalid patterns, verbs, or technology names
        INVALID_COMPANY_PATTERNS = [
            r"\bused\b",
            r"\bworked\b",
            r"\bbuilt\b",
            r"\bcreated\b",
            r"\bdeveloped\b",
            r"\bdevelop\b",
            r"\bhtml\b",
            r"\bcss\b",
            r"\breact\b",
            r"\bnode\.?js\b",
            r"\bbackend\b",
            r"\bfrontend\b"
        ]
        if any(re.search(pat, company_lower) for pat in INVALID_COMPANY_PATTERNS):
            return False
        
        # Reject description sentences/heuristics that are clearly not company names
        desc_words = {
            "developed", "creating", "created", "designed", "designing", "implemented", "implementing",
            "integrated", "integrating", "building", "built", "using", "collaborated", "collaborating",
            "coordinated", "coordinating", "managed", "managing", "led", "leading", "assisted", "assisting",
            "gained", "gaining", "learned", "focused", "focusing", "responsibilities", "duties",
            "projects", "academic", "achievements", "contributed", "contributing", "solved", "solving",
            "published", "publishing", "writing", "written", "testing", "tested", "bidding", "proposal",
            "outreach", "negotiation", "closing", "relationships", "partners",
            "study", "provided", "intermediaries", "manufacturers", "manufacturing", "trading", "staying", "updated",
            "passionate", "driving", "growth", "strategic", "brand", "sales", "marketing", "portfolio", "highlights",
            "included", "assets", "casa"
        }
        if any(w in words for w in desc_words) and not has_strong_suffix:
            return False
            
        # Reject description phrases
        description_phrases = [
            "my role", "it is a", "such as", "provided by", "staying updated", "based company", "worked with",
            "study of", "provided by client", "documents provided", "organization such as", "organizations such as"
        ]
        if any(p in company_lower for p in description_phrases):
            return False

        # Reject company names containing 4-digit years (e.g. "Fab 2025")
        if re.search(r'\b(19|20)\d{2}\b', company_lower):
            return False

        # Reject generic IT Services/Development terms if they are the only words
        generic_terms = {
            "it services", "it solutions", "software services", "software solutions", "web services",
            "web solutions", "consulting services", "technology services", "technology solutions",
            "software development", "web development", "app development", "mobile development",
            "design services", "marketing services", "digital marketing"
        }
        if company_lower in generic_terms:
            return False
            
        # Reject if company name matches/contains candidate name words
        candidate_words = set()
        if hasattr(self, "candidate_name") and self.candidate_name:
            candidate_words.update(
                w for w in re.findall(r'\b\w+\b', self.candidate_name.lower()) if len(w) > 2
            )
            
        header_source = getattr(self, "full_text", text)
        header_lines = [l.strip() for l in header_source.split("\n") if l.strip()]
        for line in header_lines[:4]:
            if len(line) < 35 and not any(c in line for c in "@:/.0123456789+()"):
                candidate_words.update(
                    w for w in re.findall(r'\b\w+\b', line.lower()) if len(w) > 2
                )
                
        if candidate_words:
            company_words_set = {w for w in words if len(w) > 2}
            matching_names = company_words_set.intersection(candidate_words)
            if matching_names and not has_strong_suffix:
                return False

        # Reject generic single words
        if len(words) == 1 and words[0] in {
            "technology", "technologies", "systems", "system", "solutions", "solution",
            "services", "service", "and", "with", "for", "at", "about", "the", "an", "a",
            "in", "of", "by", "to", "from", "on", "as", "phone", "email", "address",
            "contact", "remote", "freelance", "highlights", "summary", "profile",
            "objective", "skills", "continuous", "project", "projects", "work", "job", "position",
            "staff", "hr", "recruiter", "developer", "designer", "manager", "lead", "engineer",
            "backend", "frontend", "intern", "associate", "analyst", "specialist", "coordinator",
            "officer", "consultant", "trainee", "admin", "assistant", "expert", "support", "technician",
            "teacher", "lecturer", "professor", "instructor", "tutor", "trainer", "present", "current",
            "assets", "casa"
        }:
            return False
            
        # Reject fields of study and degree certifications
        study_fields = {
            "computer engineering", "information technology", "software engineering", "computer science",
            "mechanical engineering", "civil engineering", "electrical engineering", "electronics engineering",
            "chemical engineering", "business administration", "data science", "machine learning",
            "artificial intelligence", "cyber security", "cloud computing"
        }
        if company_lower in study_fields:
            return False

        # Reject generic noise word intersections
        generic_noise_words = {
            "knowledge", "skills", "capabilities", "experience", "summary", "profile", "objective",
            "projects", "education", "hobbies", "interests", "activities", "details", "contact",
            "certificate", "certification", "degree", "diploma", "training", "course", "placement",
            "major", "specialization", "curriculum", "syllabus", "internship", "project"
        }
        if any(w in words for w in generic_noise_words) and not has_strong_suffix:
            return False

        # Reject invalid company substring patterns
        INVALID_COMPANY_PATTERNS = [
            "communication",
            "leadership",
            "critical thinking",
            "problem solving",
            "responsible for",
            "experience with",
            "rest api",
            "ci/cd",
            "certification",
            "skills",
            "strength",
            "summary",
            "cross-functional",
            "strategic planning",
            "resource management",
            "teamwork",
            "collaboration",
            "project management"
        ]
        if any(p in company_lower for p in INVALID_COMPANY_PATTERNS):
            return False

        # 7. Additional Blacklist check
        INVALID_COMPANIES_SET = {
            "mern", "react", "firebase", "sap", "bde", "admin", "dice", "linkedin",
            "upwork", "freelancer", "fiverr", "behance", "peopleperhour", "guru", "contra",
            "github", "gitlab", "bitbucket", "trello", "jira", "confluence", "slack", "zoom",
            "teams", "postman", "figma", "canva", "google play", "play store", "app store",
            "remote job", "continuous learning", "self-employed", "self employed",
            "academic project", "project work", "key highlights", "highlights", "summary",
            "profile", "objective", "skills", "technologies"
        }
        if company_lower in INVALID_COMPANIES_SET:
            return False
            
        if any(w in INVALID_COMPANIES_SET for w in words):
            if len(words) == 1 or company_lower in {"mern stack", "react js", "react native", "firebase console"}:
                return False
                
        # 8. Reject technology names and skill keywords
        fallback_tech = {
            "python", "mysql", "mongodb", "postgresql", "sqlite", "oracle", "redis",
            "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "git", "bootstrap",
            "tailwind", "jquery", "flutter", "dart", "spring boot", "express", "node",
            "django", "flask", "fastapi", "laravel", "php", "java", "javascript",
            "typescript", "html", "css", "c++", "c#", "c", "c/c++", "android", "ios", "web"
        }
        all_tech = TECH_KEYWORDS | fallback_tech
        
        if company_lower in all_tech or company_lower.replace(" ", "") in all_tech:
            return False
            
        if len(words) == 1 and words[0] in all_tech:
            return False
            
        # 9. Reject short uppercase tokens
        INVALID_SHORT_TOKENS = {
            "BDE", "BCA", "MCA", "IT", "HR", "BE", "ME", "CE", "EE", "CSE", "ECE",
            "BCOM", "MCOM", "BSC", "MSC", "PHD", "MBA", "SSC", "HSC", "CBSE", "GSEB",
            "ICSE", "API", "REST", "SQL", "AWS", "GCP", "PHP", "CSS", "XML", "OWL",
            "MVC", "LWC", "CPQ", "CRM", "KYC", "PAN", "GST", "OTP", "TTL", "SOP",
            "POS", "EDC", "UAT", "UI", "UX", "CI", "CD", "SEO", "SaaS", "ERP", "DB",
            "DBMS", "RAG", "LLM", "AI", "ML", "DL", "CV", "NLP", "GAN", "VAE", "OCR",
            "SOW", "IIS", "SSL", "DNS", "LTI", "CTF"
        }
        if company_clean in INVALID_SHORT_TOKENS or company_clean.upper() in INVALID_SHORT_TOKENS:
            return False
            
        if len(company_clean) <= 2:
            return False
            
        if len(company_clean) <= 4 and company_clean.isupper():
            if company_clean not in {"TCS", "IBM", "HDFC", "WIPRO", "L&T", "CTS", "CGI", "HSBC", "ISRO", "BARC"}:
                if not any(c in company_lower for c in "aeiouy"):
                    return False
                    
        # 10. Detect organization patterns
        ORG_MARKERS = {
            "ltd", "limited", "inc", "corp", "corporation", "solutions", "services",
            "technologies", "technology", "global", "pvt", "llp", "systems", "bank",
            "consultancy", "group", "labs", "infotech", "software", "soft", "consulting",
            "agency", "industries", "industry", "institute", "academy", "university",
            "college", "school", "hospital", "technolab", "softech", "infosoft", "solutions",
            "engineering", "engineers", "developers", "foundation", "ventures", "labs", "lab"
        }
        has_org_marker = any(w in ORG_MARKERS for w in words)
        
        if has_org_marker:
            if company_lower in {"firebase console", "github actions"}:
                return False
            return True
            
        # 11. Heuristics: context validation
        text_lower = text.lower()
        company_pattern = re.escape(company_lower)
        
        occurrences = [m.start() for m in re.finditer(rf"\b{company_pattern}\b", text_lower)]
        if not occurrences:
            occurrences = [m.start() for m in re.finditer(company_pattern, text_lower)]
            
        if not occurrences:
            return False
            
        is_valid_context = False
        for pos in occurrences:
            start_win = max(0, pos - 80)
            end_win = min(len(text), pos + len(company_clean) + 80)
            window = text_lower[start_win:end_win]
            
            client_patterns = [
                rf"clients?\s+(?:like|including|for)?\s+(?:[^.!?]*\b)?{company_pattern}",
                rf"worked\s+(?:for|with)\s+clients?\s+(?:[^.!?]*\b)?{company_pattern}",
                rf"client\s*:\s*{company_pattern}"
            ]
            is_client = any(re.search(p, window) for p in client_patterns)
            if is_client:
                continue
                
            has_employment_preposition = bool(re.search(
                rf"\b(?:at|in|for|with|from|joined|employed\s+at|intern\s+at|internship\s+at|developer\s+at|engineer\s+at)\s+(?:[^.!?]*\b)?{company_pattern}",
                window
            ))
            
            has_date_nearby = bool(self.DATE_RE.search(window))
            has_role_nearby = any(r in window for r in self.ROLE_MARKERS)
            
            line_start_pos = text_lower.rfind("\n", 0, pos) + 1
            is_at_line_start = (pos - line_start_pos) <= 5
            
            if (has_employment_preposition and has_date_nearby) or \
               (has_employment_preposition and has_role_nearby) or \
               (has_role_nearby and has_date_nearby) or \
               (is_at_line_start and (has_date_nearby or has_role_nearby)):
                is_valid_context = True
                break
                
        return is_valid_context

    def _contains_many_verbs(self, company_lower: str) -> bool:
        words = company_lower.split()
        VERB_WORDS = {
            "use", "used", "using", "work", "worked", "working", "develop", "developed", "developing",
            "build", "built", "building", "create", "created", "creating", "design", "designed", "designing",
            "implement", "implemented", "implementing", "integrate", "integrated", "integrating",
            "manage", "managed", "managing", "lead", "led", "leading", "spearhead", "spearheaded", "spearheading",
            "conduct", "conducted", "conducting", "coordinate", "coordinated", "coordinating",
            "maintain", "maintained", "maintaining", "provide", "provided", "providing",
            "gain", "gained", "gaining", "learn", "learned", "learning", "enhance", "enhanced", "enhancing",
            "solve", "solved", "solving", "analyze", "analyzed", "analyzing", "prepare", "prepared", "preparing",
            "test", "tested", "testing", "write", "wrote", "writing", "make", "made", "making", "keep", "kept", "keeping",
            "run", "ran", "running", "get", "got", "getting", "help", "helped", "helping", "assist", "assisted", "assisting",
            "monitor", "monitored", "monitoring", "drive", "drove", "driving", "deliver", "delivered", "delivering",
            "support", "supported", "supporting", "collaborate", "collaborated", "collaborating",
            "focus", "focused", "focusing", "optimize", "optimized", "optimizing", "ensure", "ensured", "ensuring",
            "contribute", "contributed", "contributing", "boost", "boosted", "boosting", "perform", "performed", "performing",
            "secure", "secured", "securing", "expand", "expanded", "expanding", "recognize", "recognized", "recognizing",
            "achieve", "achieved", "achieving", "sales", "selling", "sold"
        }
        EXCLUDED_COMPANY_WORDS = {
            "learning", "consulting", "engineering", "trading", "marketing", "solutions",
            "services", "systems", "group", "labs", "infotech", "software", "design", "co",
            "corporation", "limited", "ltd", "pvt", "llp", "llc", "gmbh"
        }
        verb_count = 0
        for w in words:
            w_clean = w.strip(".,;:()[]{}")
            if w_clean in EXCLUDED_COMPANY_WORDS:
                continue
            is_verb = False
            if w_clean in VERB_WORDS:
                is_verb = True
            elif len(w_clean) > 3:
                if w_clean.endswith("ed") and w_clean not in {"limited", "united", "bed", "red", "shed", "feed", "speed", "seed"}:
                    is_verb = True
                elif w_clean.endswith("ing") and w_clean not in {"banking", "manufacturing", "publishing", "building", "catergoring", "ring", "wing", "sing", "thing", "spring", "king", "ping"}:
                    is_verb = True
            if is_verb:
                verb_count += 1
        return verb_count >= 2

    def _is_all_lowercase_sentence(self, s: str) -> bool:
        letters = [c for c in s if c.isalpha()]
        if not letters:
            return False
        return all(c.islower() for c in letters)

    def _normalize_to_yyyy_mm(self, s: str) -> str:
        s = s.strip().lower()
        if not s:
            return ""
        if s in {"present", "current", "ongoing", "now"}:
            return "Present"
            
        MONTHS_MAP = {
            "jan": "01", "january": "01",
            "feb": "02", "february": "02",
            "mar": "03", "march": "03",
            "apr": "04", "april": "04",
            "may": "05",
            "jun": "06", "june": "06",
            "jul": "07", "july": "07",
            "aug": "08", "august": "08",
            "sep": "09", "september": "09", "sept": "09",
            "oct": "10", "october": "10",
            "nov": "11", "november": "11",
            "dec": "12", "december": "12"
        }
        
        # 1. Match MM/YYYY or MM-YYYY (e.g. 01/2025, 12-2021)
        m = re.match(r'^(0?[1-9]|1[0-2])[-/](\d{4})$', s)
        if m:
            month = m.group(1).zfill(2)
            year = m.group(2)
            return f"{year}-{month}"
            
        # 2. Match YYYY-MM (e.g. 2021-12)
        m = re.match(r'^(\d{4})[-/](0?[1-9]|1[0-2])$', s)
        if m:
            year = m.group(1)
            month = m.group(2).zfill(2)
            return f"{year}-{month}"
            
        # 3. Match Month Name + Year (e.g. jan 2022, january 2022)
        m = re.match(r'^([a-z]{3,9})\s*[-/,\s]\s*(\d{4})$', s)
        if m:
            month_name = m.group(1)
            year = m.group(2)
            if month_name in MONTHS_MAP:
                return f"{year}-{MONTHS_MAP[month_name]}"
                
        # 4. Match Year + Month Name (e.g. 2022 jan)
        m = re.match(r'^(\d{4})\s*[-/,\s]\s*([a-z]{3,9})$', s)
        if m:
            year = m.group(1)
            month_name = m.group(2)
            if month_name in MONTHS_MAP:
                return f"{year}-{MONTHS_MAP[month_name]}"
                
        # 5. Match YYYY (e.g. 2022)
        m = re.match(r'^(\d{4})$', s)
        if m:
            return m.group(1)
            
        # Fallback: search for 4-digit year and month name
        m_year = re.search(r'\b(19|20)\d{2}\b', s)
        if m_year:
            year = m_year.group(0)
            for month_name, month_num in MONTHS_MAP.items():
                if month_name in s:
                    return f"{year}-{month_num}"
            return year
            
        return s.title()

    def _empty_job(self) -> Dict[str, Any]:
        return {
            "company": "",
            "location": "",
            "role": "",
            "duration": "",
            "start_date": "",
            "end_date": "",
            "description": ""
        }

    def _distinguish_role_company(self, role: str, company: str) -> Tuple[str, str]:
        """Heuristic to swap role and company if they look misidentified."""
        role = role.strip()
        company = company.strip()
        
        if not role and not company:
            return role, company
            
        r_role = self._role_score(role)
        r_company = self._role_score(company)
        c_role = self._company_score(role)
        c_company = self._company_score(company)
        
        should_swap = False
        
        # Case 1: Both are present, and they are clearly swapped
        if role and company:
            # role is more company-like than role-like AND company is more role-like than company-like
            if c_role > r_role and r_company > c_company:
                should_swap = True
            # Or if role has strong company marker and company has strong role marker
            elif c_role >= 2 and r_company >= 2 and (c_role > c_company or r_company > r_role):
                should_swap = True
            # Or if role has strong company marker, and company is not company-like
            elif c_role >= 2 and c_company == 0 and r_role == 0:
                should_swap = True
            # Or if company has strong role marker, and role is not role-like
            elif r_company >= 2 and r_role == 0 and c_company == 0:
                should_swap = True
                
        # Case 2: role is empty, but company looks like a role
        elif not role and company:
            if r_company > c_company and r_company >= 2:
                should_swap = True
                
        # Case 3: company is empty, but role looks like a company
        elif not company and role:
            if c_role > r_role and c_role >= 2:
                should_swap = True
                
        if should_swap:
            log.info(f"Swapping role and company: role='{role}', company='{company}' -> role='{company}', company='{role}'")
            return company, role
            
        return role, company

    def _role_score(self, s: str) -> int:
        if not s:
            return 0
        low = s.lower()
        strong_count = sum(1 for m in self.STRONG_ROLE_MARKERS if re.search(rf'\b{re.escape(m)}\b', low))
        role_count = sum(1 for m in self.ROLE_MARKERS if re.search(rf'\b{re.escape(m)}\b', low))
        return strong_count * 2 + role_count

    def _company_score(self, s: str) -> int:
        if not s:
            return 0
        low = s.lower()
        strong_count = sum(1 for m in self.STRONG_COMPANY_MARKERS if re.search(rf'\b{re.escape(m)}\b', low))
        co_count = sum(1 for m in self.COMPANY_MARKERS if re.search(rf'\b{re.escape(m)}\b', low))
        return strong_count * 2 + co_count

    def _split_merged_company_role(self, text: str) -> Tuple[str, str]:
        """Splits a single string containing both company and role details."""
        text = text.strip()
        if not text:
            return "", ""
            
        # 1. Split by common separators: / , | , - , at
        for sep in [" / ", " | ", " - ", " – ", " — ", " at ", " At "]:
            if sep in text:
                parts = [p.strip() for p in text.split(sep) if p.strip()]
                if len(parts) >= 2:
                    # Classify each part
                    r_parts = [self._role_score(p) for p in parts]
                    c_parts = [self._company_score(p) for p in parts]
                    
                    # Find the best role part and best company part
                    best_role_idx = -1
                    best_role_score = -1
                    best_co_idx = -1
                    best_co_score = -1
                    
                    for idx, (r_s, c_s) in enumerate(zip(r_parts, c_parts)):
                        if r_s > c_s and r_s > best_role_score:
                            best_role_score = r_s
                            best_role_idx = idx
                        if c_s > r_s and c_s > best_co_score:
                            best_co_score = c_s
                            best_co_idx = idx
                            
                    if best_role_idx != -1 and best_co_idx != -1 and best_role_idx != best_co_idx:
                        role = parts[best_role_idx]
                        company = parts[best_co_idx]
                        return role, company
                        
                    if len(parts) == 2:
                        p0_r, p0_c = r_parts[0], c_parts[0]
                        p1_r, p1_c = r_parts[1], c_parts[1]
                        if p0_r > p0_c and p0_r >= 2 and p1_c >= p1_r:
                            return parts[0], parts[1]
                        if p1_r > p1_c and p1_r >= 2 and p0_c >= p0_r:
                            return parts[1], parts[0]
                            
        # 2. Split at strong company markers
        words = text.split()
        for idx, w in enumerate(words):
            clean_w = w.lower().strip(".,;:()[]{}")
            if clean_w in self.STRONG_COMPANY_MARKERS:
                company_part = " ".join(words[:idx+1]).strip(" ,/|-–—")
                role_part = " ".join(words[idx+1:]).strip(" ,/|-–—")
                if company_part and role_part:
                    if self._role_score(role_part) > 0 or len(role_part.split()) >= 2:
                        return role_part, company_part
                        
        # 3. Check for prefix company and suffix role
        for idx in range(1, len(words)):
            prefix = " ".join(words[:idx])
            suffix = " ".join(words[idx:])
            if self._company_score(prefix) >= 2 and self._role_score(suffix) >= 2:
                return suffix, prefix
                
        return "", ""

    def _clean_swapped_or_merged_roles(self, job: Dict[str, Any], text: str) -> None:
        role = job.get("role", "").strip()
        company = job.get("company", "").strip()
        
        # 0. Clean locations and dates out of role and company first
        if role and self._is_location_line(role):
            job["location"] = self._append_unique(job.get("location", ""), role)
            role = ""
        if company and self._is_location_line(company):
            job["location"] = self._append_unique(job.get("location", ""), company)
            company = ""
            
        if role and self._is_date_only_line(role):
            job["duration"] = self._append_unique(job.get("duration", ""), role, sep=" ")
            role = ""
        if company and self._is_date_only_line(company):
            job["duration"] = self._append_unique(job.get("duration", ""), company, sep=" ")
            company = ""
            
        # 1. Check if either role or company field contains a merged combination of both
        if role:
            split_r_role, split_r_co = self._split_merged_company_role(role)
            if split_r_role and split_r_co:
                role = split_r_role
                if not company or self._company_score(company) < self._company_score(split_r_co):
                    company = split_r_co
                    
        if company:
            split_c_role, split_c_co = self._split_merged_company_role(company)
            if split_c_role and split_c_co:
                company = split_c_co
                if not role or self._role_score(role) < self._role_score(split_c_role):
                    role = split_c_role
                    
        # 2. Swap role and company if they are misidentified
        role, company = self._distinguish_role_company(role, company)
        
        # 2.5 If role is strongly company-like (no role markers at all), it is a company name/suffix.
        # We should merge/move it to company.
        if role and self._company_score(role) >= 2 and self._role_score(role) == 0:
            if company:
                if role.lower() not in company.lower() and company.lower() not in role.lower():
                    clean_role = role.lower().strip(".()[]{} ")
                    if clean_role in {"pvt ltd", "ltd", "pvt. ltd", "llc", "llp", "inc", "corp", "corporation"}:
                        company = f"{company} {role}"
                    else:
                        company = f"{role} - {company}"
                else:
                    if len(role) > len(company):
                        company = role
            else:
                company = role
            role = ""
            
        # 3. Double check: if company is actually a role (e.g. both are roles)
        if company:
            company_words = set(re.findall(r'\b\w+\b', company.lower()))
            is_company_actually_role = any(w in self.ROLE_MARKERS for w in company_words)
            has_company_indicator = any(w in self.COMPANY_MARKERS for w in company_words)
            
            if is_company_actually_role and not has_company_indicator:
                if role:
                    text_lower = text.lower()
                    pos_role = text_lower.find(role.lower())
                    pos_company = text_lower.find(company.lower())
                    if pos_company != -1 and pos_role != -1:
                        if pos_company < pos_role:
                            role = f"{company} {role}"
                        else:
                            role = f"{role} {company}"
                    else:
                        role = f"{company} {role}"
                else:
                    role = company
                company = ""
                
        # Clean locations and dates out of role and company again just in case
        if role and self._is_location_line(role):
            job["location"] = self._append_unique(job.get("location", ""), role)
            role = ""
        if company and self._is_location_line(company):
            job["location"] = self._append_unique(job.get("location", ""), company)
            company = ""
            
        role = role.strip(" ,.-–—|/()[]{}") 
        company = company.strip(" ,.-–—|/()")
        
        # Strip work-type and duration parentheticals from role
        # e.g. "(Full-time)", "(Part-time)", "(2 Months)", "(Internship)", etc.
        _WORK_TYPE_PAT = re.compile(
            r'\s*\(\s*(?:full[- ]?time|part[- ]?time|contract|freelance|internship|intern|' +
            r'permanent|temporary|remote|onsite|on[- ]?site|hybrid|wfh|' +
            r'\d+\s*(?:months?|years?|yrs?|weeks?))\s*\)',
            re.I
        )
        role = _WORK_TYPE_PAT.sub('', role).strip()
        # Fix unclosed parentheses at end of role
        if '(' in role and role.count('(') != role.count(')'):
            role = re.sub(r'\s*\([^)]*$', '', role).strip()

        job["role"] = role
        job["company"] = company

    def _assign_post_date_headers(self, job: Dict[str, Any], post_headers: List[str]) -> None:
        for line in post_headers:
            line_clean = line.strip(" -–—|,()")
            if not line_clean:
                continue
            
            # If it's a location line, append to location
            if self._is_location_line(line_clean):
                job["location"] = self._append_unique(job["location"], line_clean)
                continue
                
            # If we don't have a role yet, and the line looks like a role
            if not job["role"] and self._line_looks_like_role(line_clean):
                job["role"] = line_clean
            # If we have a role but no company, and the line doesn't look like a role
            elif job["role"] and not job["company"] and not self._line_looks_like_role(line_clean):
                job["company"] = line_clean
            # If we have a company but no role, and the line looks like a role
            elif job["company"] and not job["role"] and self._line_looks_like_role(line_clean):
                job["role"] = line_clean
            # Fallback
            elif not job["role"]:
                job["role"] = line_clean
            elif not job["company"]:
                job["company"] = line_clean
            else:
                if self._line_looks_like_role(line_clean):
                    job["role"] = self._append_unique(job["role"], line_clean, sep=" / ")
                else:
                    job["description"] = self._append_sentence(job["description"], line_clean)

    def _parse_date_range(self, date_str: str) -> Tuple[str, str, str]:
        """Standardizes date ranges and cleans noise."""
        if not date_str:
            return "", "", ""
        
        match = self.DATE_RE.search(date_str)
        if match:
            clean_date_str = match.group(0).strip()
        else:
            clean_date_str = date_str.strip()

        # Handle open-ended dates like "Sep 2025 -"
        if clean_date_str.endswith("-") or clean_date_str.endswith("–"):
             return clean_date_str.rstrip("-–").strip(), "Present", clean_date_str + " Present"
             
        parts = re.split(r'\s+(?:[-–—]|to|until)\s+|\s+[-–—]\s*', clean_date_str, flags=re.I)
        parts = [p.strip() for p in parts if p.strip()]
        
        start = parts[0] if len(parts) > 0 else ""
        end = parts[1] if len(parts) > 1 else ""
        
        if not end and ("present" in clean_date_str.lower() or "current" in clean_date_str.lower()):
            end = "Present"
            
        return start, end, clean_date_str

    def _clean_description(self, desc: str) -> str:
        """Merges lines and cleans noise from descriptions."""
        if not desc: return ""
        # Remove redundant whitespace and newlines
        desc = desc.replace("\n", " ")
        desc = re.sub(r'\s+', ' ', desc)
        # Remove leading/trailing artifacts like bullets and leading parentheses
        desc = re.sub(r'^[•\-\*\s,;|\)]+', '', desc)
        return desc.strip()

    def _is_company_description_sentence(self, line: str) -> bool:
        low = line.lower().strip()
        if low.startswith(("a ", "an ", "the ", "our ")):
            if any(w in low for w in {"company", "provider", "developer", "solutions", "services", "firm", "agency", "organization", "platform", "specialist"}):
                if any(w in low for w in {"specializing", "focusing", "offering", "providing", "dedicated to", "specializes", "focuses", "offers", "provides"}):
                    return True
                if len(low.split()) >= 6:
                    return True
        return False

    def _classify_line(self, line: str) -> str:
        line_stripped = line.strip()
        if not line_stripped:
            return "EMPTY"
            
        if self._is_company_description_sentence(line_stripped):
            return "DESCRIPTION"
            
        # Check for bullet point starters
        is_bullet = False
        if re.match(r'^[•\-\*\u2022⚫■★]\s*', line_stripped):
            is_bullet = True
        elif re.match(r'^\d+\.\s+', line_stripped):
            is_bullet = True
            
        # Clean prefix to check content
        content_line = re.sub(r'^[•\-\*\u2022⚫■★]\s*', '', line_stripped).strip()
        content_line = re.sub(r'^\d+\.\s+', '', content_line).strip()
        content_lower = content_line.lower()
        
        if not content_line:
            return "EMPTY"
            
        # Treat parenthetical details (that don't start with a date range) as description lines
        if content_line.startswith("("):
            return "DESCRIPTION"
            
        # Check if the line is a description heading (e.g. Roles and Responsibilities)
        if self._is_description_heading(content_line):
            return "DESCRIPTION"
            
        # Check for date pattern
        if self._is_date_only_line(content_line):
            return "DATE"
            
        # Check for location
        if self._is_location_line(content_line):
            return "LOCATION"
            
        # Check description starters and verbs
        words = content_lower.split()
        first_word = words[0] if words else ""
        first_word_clean = first_word.strip(".,;:()[]")
        second_word = words[1] if len(words) > 1 else ""
        second_word_clean = second_word.strip(".,;:()[]")
        
        is_desc_start = False
        if first_word_clean in self.DESCRIPTION_STARTERS:
            is_desc_start = True
        elif first_word_clean.endswith("ed") and len(first_word_clean) > 3:
            is_desc_start = True
        elif first_word_clean.endswith("ing") and len(first_word_clean) > 3:
            is_desc_start = True
        elif first_word_clean in {"conducted", "led", "built", "drove", "wrote", "made", "kept", "ran", "got", "helped", "assisted", "monitored", "provided", "gained", "learned", "enhanced", "solved", "analyzed", "prepared", "coordinated"}:
            is_desc_start = True
        elif first_word_clean.endswith("ly") and second_word_clean:
            if second_word_clean.endswith("ed") or second_word_clean.endswith("ing") or second_word_clean in self.DESCRIPTION_STARTERS or second_word_clean in {"conducted", "led", "built", "drove", "wrote", "made", "provided", "gained", "learned", "enhanced", "solved", "analyzed", "prepared", "coordinated"}:
                is_desc_start = True
            
        if is_bullet:
            return "BULLET_POINT"
            
        if is_desc_start or len(content_line) > 85:
            return "DESCRIPTION"
            
        # Score-based classification
        r_score = self._role_score(content_line)
        c_score = self._company_score(content_line)
        
        if r_score > c_score:
            return "ROLE"
        elif c_score > r_score:
            return "COMPANY"
        elif r_score > 0:
            return "ROLE"
            
        # Default fallback
        if len(content_line) < 60:
            raw_words = content_line.split()
            if raw_words and raw_words[0][0].isupper():
                return "COMPANY"
            return "DESCRIPTION"
            
        return "DESCRIPTION"

    def _rule_based_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Line-aware parser for common resume experience layouts."""
        log.info("Running rule-based parser for Experience.")
        
        entries = []
        current_job = None
        has_description_lines = False

        def commit():
            nonlocal current_job, has_description_lines
            if not current_job:
                return
            
            # 1. Clean swapped or merged roles first (splits, location, dates, swaps)
            self._clean_swapped_or_merged_roles(current_job, text)
            
            # 2. Company validation layer (on the cleaned company name)
            if current_job["company"] and not self._is_valid_company(current_job["company"], text):
                log.info(f"Rejecting invalid company name in fallback: {current_job['company']}")
                current_job["company"] = ""
            
            start, end, dur = self._parse_date_range(current_job["duration"])
            current_job["duration"] = dur
            current_job["start_date"] = self._normalize_to_yyyy_mm(start)
            current_job["end_date"] = self._normalize_to_yyyy_mm(end)
            current_job["description"] = self._clean_description(current_job["description"])
            
            if current_job["company"] or current_job["role"]:
                entries.append(current_job)
                
            current_job = None
            has_description_lines = False

        duration_prefix_re = re.compile(
            r'^(?P<duration>\d+(?:\.\d+)?\s*(?:months?|yrs?|years?))\s+(?:in\s+|at\s+|for\s+|of\s+)?(?P<rest>.+)$',
            re.I
        )

        # First, pre-classify all lines and handle inline dates
        processed_lines = []
        for raw_line in text.split("\n"):
            clean = self._clean_line(raw_line)
            if not clean:
                continue
            if self._is_contact_noise(clean) and not self.DATE_RE.search(clean):
                continue
            if self._is_education_noise(clean):
                continue
                
            # If line contains a date and it's not date-only, extract the date
            date_match = self.DATE_RE.search(clean)
            is_date_only = self._is_date_only_line(clean)
            
            extracted_date = ""
            line_text = clean
            
            if date_match and not is_date_only:
                extracted_date = date_match.group(0)
                line_text = (clean[:date_match.start()] + " " + clean[date_match.end():]).strip(" -–—|,()")
                # Re-clean multiple spaces
                line_text = re.sub(r'\s+', ' ', line_text)
                
            # Check for duration prefix at the beginning of line_text
            dur_match = duration_prefix_re.match(line_text)
            if dur_match:
                extracted_date = self._append_unique(extracted_date, dur_match.group("duration"), sep=" ")
                line_text = dur_match.group("rest").strip(" -–—|,()")
                line_text = re.sub(r'\s+', ' ', line_text)
                
            # If the line is empty after stripping date/duration, it was practically a date-only line
            if not line_text:
                cls = "DATE"
            else:
                cls = self._classify_line(line_text)
                
            processed_lines.append({
                "raw": clean,
                "text": line_text,
                "class": cls,
                "date": extracted_date
            })

        i = 0
        while i < len(processed_lines):
            item = processed_lines[i]
            line_text = item["text"]
            cls = item["class"]
            extracted_date = item["date"]
            
            # If we are already in the description section of a job,
            # we should only treat ROLE or COMPANY lines as starting a new job
            # if they are accompanied by a date range nearby (either inline or in adjacent lines).
            # Otherwise, they are likely false positives (capitalized text or role keywords in descriptions).
            if current_job is not None and has_description_lines and cls in {"ROLE", "COMPANY"}:
                has_date = False
                for j in range(i, min(len(processed_lines), i + 4)):
                    if processed_lines[j]["class"] == "DATE" or processed_lines[j]["date"]:
                        has_date = True
                        break
                if not has_date:
                    cls = "DESCRIPTION"

            # Start/commit new job conditions
            should_start_new_job = False
            
            if current_job is not None:
                # 1. If we see a DATE line and we already have duration
                if cls == "DATE" and current_job["duration"]:
                    should_start_new_job = True
                # 2. If we see an inline date and we already have duration
                elif extracted_date and current_job["duration"]:
                    should_start_new_job = True
                # 3. If we see a ROLE or COMPANY line and description has started
                elif (cls == "ROLE" or cls == "COMPANY") and has_description_lines:
                    should_start_new_job = True
                # 4. If we see a ROLE or COMPANY line and both role and company are filled
                elif (cls == "ROLE" or cls == "COMPANY") and current_job["role"] and current_job["company"]:
                    should_start_new_job = True
                # 5. If we see a COMPANY line and company is already filled
                elif cls == "COMPANY" and current_job["company"]:
                    should_start_new_job = True
                # 6. If we see a ROLE line and role is already filled
                elif cls == "ROLE" and current_job["role"]:
                    should_start_new_job = True
            else:
                # If current_job is None, any header/date starts a new job
                if cls in {"ROLE", "COMPANY", "DATE"} or extracted_date:
                    current_job = self._empty_job()
                    
            if should_start_new_job:
                commit()
                current_job = self._empty_job()
                
            if current_job is None:
                i += 1
                continue
                
            # Assign extracted date if present
            if extracted_date:
                current_job["duration"] = self._append_unique(current_job["duration"], extracted_date, sep=" ")
                
            # Process the line text based on classification
            if cls == "DATE":
                current_job["duration"] = self._append_unique(current_job["duration"], line_text, sep=" ")
                
            elif cls == "LOCATION":
                current_job["location"] = self._append_unique(current_job["location"], line_text)
                
            elif cls in {"ROLE", "COMPANY"}:
                r, c, loc = self._parse_header_text(line_text)
                if loc:
                    current_job["location"] = self._append_unique(current_job["location"], loc)

                # Only trust the r,c split when:
                # - there is an explicit separator in the original text, OR
                # - the extracted company has a real org marker, OR
                # - the extracted company does NOT look like a role, but the role part DOES
                #   (catches companies without org markers like "Spark to Idea", "Gide.Ai")
                has_separator = any(sep in line_text for sep in [" - ", " – ", " — ", " | ", " at "])
                c_looks_real = c and (
                    self._company_score(c) >= 1 or
                    self._line_looks_like_company(c) or
                    # Asymmetric split: role part has role markers, company part doesn't
                    (self._role_score(r) >= 1 and self._role_score(c) == 0)
                )
                # Extra safety: never trust a split where the "company" itself looks like a role
                # and the "role" doesn't have role markers (e.g. role="Frontend", company="and WordPress Developer")
                if c_looks_real and self._role_score(c) > 0 and self._role_score(r) == 0:
                    c_looks_real = False

                if r and c and (has_separator or c_looks_real):
                    current_job["role"] = self._append_unique(current_job["role"], r, sep=" / ")
                    current_job["company"] = self._append_unique(current_job["company"], c)
                elif cls == "ROLE":
                    if has_separator:
                        if r: current_job["role"] = self._append_unique(current_job["role"], r, sep=" / ")
                        if c: current_job["company"] = self._append_unique(current_job["company"], c)
                    else:
                        current_job["role"] = self._append_unique(current_job["role"], line_text, sep=" / ")
                elif cls == "COMPANY":
                    if any(sep in line_text for sep in [" - ", " – ", " — ", " | ", " at "]):
                        if r: current_job["role"] = self._append_unique(current_job["role"], r, sep=" / ")
                        if c: current_job["company"] = self._append_unique(current_job["company"], c)
                    else:
                        current_job["company"] = self._append_unique(current_job["company"], line_text)
                        
            elif cls in {"DESCRIPTION", "BULLET_POINT"}:
                current_job["description"] = self._append_sentence(current_job["description"], line_text)
                has_description_lines = True
                
            i += 1
            
        commit()
        return entries

    def _clean_line(self, line: str) -> str:
        line = line.strip()
        line = re.sub(r'^[•\-\*\u2022]+\s*', '', line)
        line = re.sub(r'\s+', ' ', line)
        return line.strip()

    def _is_contact_noise(self, line: str) -> bool:
        low = line.lower().strip()
        if "http://" in low or "https://" in low or "www." in low:
            return True
        if low.startswith("website:") or low.startswith("linkedin:") or low.startswith("github:"):
            return True
        if re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', line):
            return True
        digits = re.sub(r'\D', '', line)
        return len(digits) >= 9 and len(line.split()) <= 6

    def _is_education_noise(self, line: str) -> bool:
        low = line.lower().strip()
        # Common educational keywords / degrees
        edu_degrees = {
            r'\bbca\b', r'\bmca\b', r'\bb\.tech\b', r'\bm\.tech\b', r'\bbe\b', r'\bme\b',
            r'\bb\.e\.?\b', r'\bm\.e\.?\b', r'\bb\.sc\b', r'\bm\.sc\b', r'\bbsc\b', r'\bmsc\b',
            r'\bmba\b', r'\bbcom\b', r'\bmcom\b', r'\bb\.com\b', r'\bm\.com\b', r'\bhsc\b',
            r'\bsslc\b', r'\bssc\b', r'\bcbse\b', r'\bgseb\b', r'\bicse\b', r'\bdiploma\b',
            r'\bdegree\b', r'\bmatric\b', r'\bgraduation\b', r'\bpost\s+graduation\b',
            r'\bbachelor\b', r'\bmaster\b', r'\bph\.?d\b', r'\beducation\b'
        }
        for deg in edu_degrees:
            if re.search(deg, low):
                return True
                
        # Grades / GPA / CGPA / Percentages
        if any(w in low for w in ["cgpa", "gpa", "grade", "percentage", "percent", "marks", "class:"]):
            return True
            
        # School / College / University names (if no role marker present)
        edu_institutions = ["college", "university", "school", "academy", "vidhyalaya", "vidyalaya", "vidhyalay", "vidyalay", "sankul", "institute", "collage"]
        study_keywords = {
            "engineering", "technology", "science", "sciences", "commerce", "arts", 
            "matric", "secondary", "higher", "primary", "education", "bachelor", 
            "master", "diploma", "degree", "studies", "administration", "management"
        }
        if any(w in low for w in edu_institutions):
            # But if there's a strong role marker, keep it (e.g. Teacher, Instructor)
            if self._line_looks_like_role(line):
                return False
            return True
                
        return False

    def _is_resume_header_noise(self, line: str) -> bool:
        words = line.split()
        if not (1 < len(words) <= 4):
            return False
        if not line.replace(" ", "").isupper():
            return False
        low = line.lower()
        return not any(marker in low for marker in self.ROLE_MARKERS | self.COMPANY_MARKERS)

    def _is_description_heading(self, line: str) -> bool:
        return self._clean_section_name(line) in {
            "roles and responsibilities", "responsibilities", "key achievements"
        }

    def _looks_like_description_start(self, line: str) -> bool:
        low = self._clean_section_name(line)
        first = low.split(" ", 1)[0] if low else ""
        return low in self.DESCRIPTION_STARTERS or first in self.DESCRIPTION_STARTERS

    def _is_date_only_line(self, line: str) -> bool:
        match = self.DATE_RE.fullmatch(line.strip())
        if match:
            return True
        compact = re.sub(r'\s+', ' ', line.strip())
        return bool(re.fullmatch(rf'{self.DATE_PART}\s*(?:[-–—]|to|until)?\s*(?:{self.DATE_PART}|present|current)', compact, re.I))

    def _find_stacked_date_index(self, lines: List[str], start_idx: int) -> Optional[int]:
        if not self._is_probable_header_line(lines[start_idx]):
            return None
        max_idx = min(len(lines), start_idx + 5)
        for j in range(start_idx + 1, max_idx):
            if self._is_date_only_line(lines[j]):
                header_lines = lines[start_idx:j]
                if any(not self._is_probable_header_line(h) for h in header_lines):
                    return None
                return j
            if self.DATE_RE.search(lines[j]) and self._is_probable_job_header(lines[j]):
                return None
        return None

    def _collect_header_after_date(self, lines: List[str], start_idx: int) -> Tuple[List[str], int]:
        header_lines = []
        i = start_idx
        while i < len(lines) and len(header_lines) < 4:
            line = lines[i]
            if self._is_date_only_line(line):
                break
            if self.DATE_RE.search(line) and self._is_probable_job_header(line):
                break
            if self._looks_like_description_start(line):
                break
            if self._is_probable_header_line(line):
                header_lines.append(line)
                i += 1
                continue
            break
        return header_lines, i

    def _is_probable_header_line(self, line: str) -> bool:
        if not line or len(line) > 110:
            return False
        if self._looks_like_description_start(line):
            return False
        low = line.lower()
        has_marker = self._line_looks_like_role(line) or self._line_looks_like_company(line)
        if (re.search(r'[!?]$', line) or "%" in line) and not has_marker:
            return False
        if re.search(r'\.$', line) and not has_marker:
            return False
        return True

    def _is_probable_job_header(self, line: str) -> bool:
        if len(line) > 220:
            return False
        low = line.lower()
        if self._looks_like_description_start(line):
            return False
        date_match = self.DATE_RE.search(line)
        has_range = bool(date_match and date_match.group(2))
        return bool(
            date_match
            and (
                self._line_looks_like_role(line)
                or self._line_looks_like_company(line)
                or (has_range and len(line.split()) <= 14)
            )
        )

    def _assign_header_lines(self, job: Dict[str, Any], header_lines: List[str]) -> None:
        clean_lines = [h.strip(" -–—|,") for h in header_lines if h and h.strip(" -–—|,")]
        if not clean_lines:
            return

        if len(clean_lines) == 1:
            role, company, location = self._parse_header_text(clean_lines[0])
            job["role"] = role
            job["company"] = company
            job["location"] = location
            return

        remaining = []
        for line in clean_lines:
            if self._is_location_line(line):
                job["location"] = self._append_unique(job["location"], line)
            else:
                remaining.append(line)

        if not remaining:
            return

        role, company, location = self._parse_header_text(remaining[0])
        if company or role:
            job["company"] = company
            job["role"] = role
            job["location"] = self._append_unique(job["location"], location)
            role_details = remaining[1:]
        else:
            job["company"] = remaining[0]
            role_details = remaining[1:]

        for detail in role_details:
            if self._looks_like_description_start(detail):
                job["description"] = self._append_sentence(job["description"], detail)
            elif job["role"] and not job["company"] and not self._line_looks_like_role(detail):
                job["company"] = detail
            elif job["company"] and not job["role"] and self._line_looks_like_role(detail):
                job["role"] = detail
            elif not job["role"]:
                job["role"] = detail
            else:
                job["role"] = self._append_unique(job["role"], detail, sep=" / ")

    def _parse_header_text(self, text: str) -> Tuple[str, str, str]:
        text = text.strip(" -–—|,/")
        text = re.sub(r'\s+', ' ', text)
        location = ""

        if not text:
            return "", "", ""

        # Parenthesis check, e.g., "Role (Company)"
        # First, strip known work-type annotations like (Full-time), (Part-time), (Contract), etc.
        WORK_TYPE_TERMS = {
            "full-time", "fulltime", "full time", "part-time", "parttime", "part time",
            "contract", "freelance", "internship", "intern", "permanent", "temporary",
            "remote", "onsite", "on-site", "hybrid", "work from home", "wfh"
        }
        text_no_worktype = re.sub(
            r'\(\s*(?:' + '|'.join(re.escape(t) for t in WORK_TYPE_TERMS) + r')\s*\)',
            '', text, flags=re.I
        ).strip(" -–—|,/")
        text_no_worktype = re.sub(r'\s+', ' ', text_no_worktype)
        paren_match = re.search(r'\((?P<inner>[^)]+)\)', text_no_worktype)
        if paren_match:
            inner = paren_match.group("inner").strip()
            outer = (text_no_worktype[:paren_match.start()] + " " + text_no_worktype[paren_match.end():]).strip(" -–—|,()")
            outer = re.sub(r'\s+', ' ', outer)
            if self._line_looks_like_company(inner) or self._line_looks_like_role(outer):
                r, c = self._order_role_company(outer, inner)
                return r, c, location
        # Use the work-type-stripped text for subsequent parsing
        text = text_no_worktype if text_no_worktype else text

        # Preposition check, e.g., "Role in Company" or "Role with Company"
        prep_match = re.search(r'\s+(?:at|in|with|for)\s+(?P<company>[^,()]+)$', text, re.I)
        if prep_match:
            comp_candidate = prep_match.group("company").strip()
            if self._line_looks_like_company(comp_candidate):
                role_candidate = text[:prep_match.start()].strip()
                r, c = self._order_role_company(role_candidate, comp_candidate)
                return r, c, location

        at_match = re.match(r'(?P<role>.+?)\s+at\s+(?P<company>.+)$', text, re.I)
        if at_match:
            return at_match.group("role").strip(), at_match.group("company").strip(), ""

        for sep in [" | ", " - ", " – ", " — "]:
            if sep in text:
                parts = [p.strip() for p in text.split(sep) if p.strip()]
                if len(parts) >= 2:
                    role, company = self._order_role_company(parts[0], parts[1])
                    return role, company, " ".join(parts[2:])

        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
            if len(parts) >= 2:
                if self._is_location_line(parts[-1]):
                    location = parts[-1]
                    rest = parts[:-1]
                    if len(rest) >= 2:
                        role, company = self._order_role_company(rest[0], rest[1])
                        return role, company, location
                    elif len(rest) == 1:
                        r, c, l = self._parse_header_text(rest[0])
                        return r, c, self._append_unique(l, location)
                else:
                    role, company = self._order_role_company(parts[0], parts[1])
                    return role, company, ""

        words = text.split()
        role_idx = self._first_role_word_index(words)
        company_marker_idx = self._company_marker_index(words)
        if company_marker_idx is not None and role_idx is not None and role_idx > company_marker_idx:
            company_end = company_marker_idx + 1
            while company_end < len(words) and re.fullmatch(r'\([^)]+\)', words[company_end]):
                company_end += 1
            middle = " ".join(words[company_end:role_idx]).strip(" ,")
            if middle and self._is_location_line(middle):
                location = self._append_unique(location, middle)
                return " ".join(words[role_idx:]), " ".join(words[:company_end]).strip(" ,"), location
            if middle and self._line_looks_like_role(middle):
                return " ".join(words[company_end:]), " ".join(words[:company_end]).strip(" ,"), location
            company_end = role_idx
            return " ".join(words[role_idx:]), " ".join(words[:company_end]).strip(" ,"), location
        if role_idx is not None:
            if role_idx <= 1:
                role_end = self._role_phrase_end(words, role_idx)
                return " ".join(words[:role_end]), " ".join(words[role_end:]), location
            return " ".join(words[role_idx:]), " ".join(words[:role_idx]), location

        return "", text, location

    def _order_role_company(self, first: str, second: str) -> Tuple[str, str]:
        first = first.strip()
        second = second.strip()
        
        r_first = self._role_score(first)
        r_second = self._role_score(second)
        c_first = self._company_score(first)
        c_second = self._company_score(second)
        
        # If the second part is company-like but the first part has no role indicators,
        # it is likely "Company - Generic/Domain description" (e.g. "Alphabi - IT Services")
        # rather than "Role - Company".
        if c_second > 0 and r_first == 0 and r_second == 0:
            return "", f"{first} - {second}"
            
        # Likewise, if the first part is company-like but the second part has no role indicators
        if c_first > 0 and r_second == 0 and r_first == 0:
            return "", f"{second} - {first}"
            
        # Standard ordering
        if r_first > c_first and c_second > r_second:
            return first, second
        if r_second > c_second and c_first > r_first:
            return second, first
            
        if r_first > r_second:
            return first, second
        if r_second > r_first:
            return second, first
            
        return first, second

    def _line_looks_like_role(self, line: str) -> bool:
        low = line.lower()
        return any(re.search(rf'\b{re.escape(marker)}\b', low) for marker in self.ROLE_MARKERS)

    def _line_looks_like_company(self, line: str) -> bool:
        low = line.lower()
        return any(re.search(rf'\b{re.escape(marker)}\b', low) for marker in self.COMPANY_MARKERS)

    def _first_role_word_index(self, words: List[str]) -> Optional[int]:
        for idx, word in enumerate(words):
            clean = word.lower().strip("().,")
            if clean in self.STRONG_ROLE_MARKERS:
                start_idx = idx
                while start_idx > 0:
                    prev_word = words[start_idx - 1].lower().strip("().,")
                    if prev_word in self.ROLE_MARKERS or prev_word in {"of", "in", "and", "&"}:
                        start_idx -= 1
                    else:
                        break
                return start_idx
        return None

    def _company_marker_index(self, words: List[str]) -> Optional[int]:
        marker_idx = None
        for idx, word in enumerate(words):
            clean = word.lower().strip("().,")
            if clean in self.COMPANY_MARKERS:
                marker_idx = idx
        return marker_idx

    def _role_phrase_end(self, words: List[str], role_idx: int) -> int:
        end = role_idx + 1
        while end < len(words):
            clean = words[end].lower().strip("().,")
            if clean in self.ROLE_MARKERS:
                end += 1
                continue
            if clean in {"and", "&"} and end + 1 < len(words):
                next_clean = words[end + 1].lower().strip("().,")
                if next_clean in self.ROLE_MARKERS:
                    end += 2
                    continue
            break
        return end

    def _is_location_line(self, line: str) -> bool:
        low = line.lower().strip("() -–—,[]{}")
        if low in {"remote", "pan-india", "india", "on-site", "onsite", "hybrid", "full-time", "part-time", "internship", "contract", "permanent", "work from home", "wfh"}:
            return True
        if re.fullmatch(r'(?:new\s+delhi|mumbai|surat|ahmedabad|pune|bangalore|hyderabad|chennai|kolkata|gurugram|noida)(?:,\s*\w+)?', low):
            return True
        if "," in line and len(line.split()) <= 5:
            # Guard: if the first comma-segment looks like an org name, it's NOT a location
            first_part = line.split(",")[0].strip().lower()
            first_words = first_part.split()
            ORG_GUARD = {
                "ltd", "limited", "inc", "corp", "corporation", "solutions", "services",
                "technologies", "technology", "pvt", "llp", "llc", "systems", "bank",
                "consultancy", "group", "labs", "infotech", "soft", "software",
                "consulting", "agency", "industries", "industry", "foundation",
                "ventures", "learning", "global"
            }
            if any(w in ORG_GUARD for w in first_words):
                return False
            return True
        return False

    def _append_unique(self, base: str, value: str, sep: str = ", ") -> str:
        value = value.strip()
        if not value:
            return base
        if not base:
            return value
        if value.lower() in base.lower():
            return base
        return f"{base}{sep}{value}"

    def _append_sentence(self, base: str, value: str) -> str:
        value = value.strip()
        if not value:
            return base
        return f"{base} {value}".strip() if base else value

    def _find_best_matching_line_index(self, query: str, lines: List[str]) -> Optional[int]:
        query_clean = query.lower().strip()
        if not query_clean:
            return None
            
        # 1. Try exact or substring match
        for idx, line in enumerate(lines):
            if query_clean in line.lower():
                return idx
                
        # 2. Try reverse substring match (line is inside query)
        for idx, line in enumerate(lines):
            line_clean = line.lower().strip()
            if len(line_clean) > 5 and line_clean in query_clean:
                return idx
                
        # 3. Try token overlap
        query_tokens = set(re.findall(r'\b\w+\b', query_clean))
        if not query_tokens:
            return None
            
        best_idx = None
        best_overlap = 0
        for idx, line in enumerate(lines):
            line_tokens = set(re.findall(r'\b\w+\b', line.lower()))
            overlap = len(query_tokens.intersection(line_tokens))
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx
                
        if best_overlap >= 1:
            return best_idx
            
        return None

    def _is_candidate_company(self, line: str) -> bool:
        line_clean = line.strip(" ,.-–—|/()[]{}")
        if not line_clean or len(line_clean) < 3:
            return False
        # Cannot be date
        if self._is_date_only_line(line_clean):
            return False
        # Cannot be location
        if self._is_location_line(line_clean):
            return False
        # Cannot be description/bullet
        cls = self._classify_line(line_clean)
        if cls in {"DESCRIPTION", "BULLET_POINT", "DATE", "LOCATION"}:
            return False
        # Let's check company score or generic capitalized words
        if self._company_score(line_clean) > 0:
            return True
        if cls == "COMPANY":
            return True
        # If it's a short title-cased line and not a role
        if len(line_clean) < 50 and self._role_score(line_clean) == 0:
            # Check if it has uppercase letter
            if any(c.isupper() for c in line_clean):
                return True
        return False

    def _is_candidate_role(self, line: str) -> bool:
        line_clean = line.strip(" ,.-–—|/()[]{}")
        if not line_clean or len(line_clean) < 3:
            return False
        if self._is_date_only_line(line_clean):
            return False
        if self._is_location_line(line_clean):
            return False
        cls = self._classify_line(line_clean)
        if cls in {"DESCRIPTION", "BULLET_POINT", "DATE", "LOCATION"}:
            return False
        if self._role_score(line_clean) > 0:
            return True
        if cls == "ROLE":
            return True
        # If it's a short line containing common role words or markers
        if len(line_clean) < 50 and any(w in self.ROLE_MARKERS for w in line_clean.lower().split()):
            return True
        return False

    def _validate_and_recover_entries(self, entries: List[Dict[str, Any]], section_text: str) -> List[Dict[str, Any]]:
        cleaned_entries = []
        lines = [l.strip() for l in section_text.split("\n")]
        
        for entry in entries:
            company = entry.get("company", "").strip()
            role = entry.get("role", "").strip()
            
            # If both are empty, discard
            if not company and not role:
                continue
                
            # If only one exists, attempt recovery
            if not company or not role:
                recovered_entry = entry.copy()
                query = role if role else company
                idx = self._find_best_matching_line_index(query, lines)
                
                if idx is not None:
                    offsets = [-1, 1, -2, 2, -3, 3]
                    for offset in offsets:
                        target_idx = idx + offset
                        if 0 <= target_idx < len(lines):
                            nearby_line = lines[target_idx]
                            
                            if not company:  # We need company
                                if self._is_candidate_company(nearby_line):
                                    temp_job = self._empty_job()
                                    temp_job["company"] = nearby_line
                                    self._clean_swapped_or_merged_roles(temp_job, section_text)
                                    if temp_job["company"]:
                                        recovered_entry["company"] = temp_job["company"]
                                        if not recovered_entry["role"] and temp_job["role"]:
                                            recovered_entry["role"] = temp_job["role"]
                                        break
                            else:  # We need role
                                if self._is_candidate_role(nearby_line):
                                    temp_job = self._empty_job()
                                    temp_job["role"] = nearby_line
                                    self._clean_swapped_or_merged_roles(temp_job, section_text)
                                    if temp_job["role"]:
                                        recovered_entry["role"] = temp_job["role"]
                                        if not recovered_entry["company"] and temp_job["company"]:
                                            recovered_entry["company"] = temp_job["company"]
                                        break
                
                # Check if it is still partially empty after recovery
                final_company = recovered_entry.get("company", "").strip()
                final_role = recovered_entry.get("role", "").strip()
                
                if not final_company or not final_role:
                    # Still partially empty -> discard
                    continue
                
                entry = recovered_entry
            
            # Re-validate validity of company name after recovery
            if entry["company"] and not self._is_valid_company(entry["company"], section_text):
                continue
                
            # Double check that we don't have empty company or role
            if not entry.get("company", "").strip() or not entry.get("role", "").strip():
                continue
                
            cleaned_entries.append(entry)
            
        # Deduplicate final entries by (company, role) to avoid duplicates from recovery of separate parts of the same job
        seen = set()
        deduped_entries = []
        for entry in cleaned_entries:
            key = (entry["company"].lower().strip(), entry["role"].lower().strip())
            if key not in seen:
                seen.add(key)
                deduped_entries.append(entry)
        return deduped_entries

    def _score_entries(self, entries: List[Dict[str, Any]]) -> int:
        score = 0
        for entry in entries:
            has_company = bool(entry.get("company"))
            has_role = bool(entry.get("role"))
            
            score += 2 if has_company else 0
            score += 2 if has_role else 0
            score += 2 if entry.get("duration") else 0
            score += 1 if entry.get("description") else 0
            
            # Bonus for complete company + role pair
            if has_company and has_role:
                score += 1
                
            if len(entry.get("description", "")) > 2500:
                score -= 3
        return score

    def _calculate_entry_confidence(self, entry: Dict[str, Any]) -> float:
        company = entry.get("company", "").strip()
        role = entry.get("role", "").strip()
        duration = entry.get("duration", "").strip()
        description = entry.get("description", "").strip()
        location = entry.get("location", "").strip()
        
        if not company and not role:
            return 0.0

        # Rule 1: company missing and no date/context
        if not company and not duration and not description:
            return 0.0

        # Rule 2: role missing and no date/context
        if not role and not duration and not description:
            return 0.0

        # 1. Evaluate Role Strength
        role_score = 0.0
        is_generic = False
        if role:
            role_clean = role.lower().strip(" ,.-–—|/()[]{}")
            role_words = role_clean.split()
            
            # Common generic role words
            generic_words = {
                "developer", "intern", "engineer", "employee", "staff", "trainee", 
                "associate", "analyst", "assistant", "member", "student", "candidate",
                "role", "job", "work", "position", "fresher"
            }
            if len(role_words) == 1 and role_words[0] in generic_words:
                is_generic = True
            elif len(role_words) == 2 and role_words[0] in {"software", "web", "app", "it"} and role_words[1] in generic_words:
                is_generic = True
                
            if is_generic:
                role_score = 0.3
            else:
                # Specific role (e.g. "Senior Frontend Developer", "SEO Specialist")
                role_score = 0.7
                # If it has strong role markers
                if any(w in self.STRONG_ROLE_MARKERS for w in role_words):
                    role_score += 0.1

        # Rule 3: only generic title exists (missing company)
        if not company and is_generic:
            # Skip unless there is both duration and description
            if duration and description:
                return 0.5
            return 0.3
                    
        # 2. Evaluate Company Strength
        company_score = 0.0
        if company:
            company_clean = company.lower().strip(" ,.-–—|/()[]{}")
            company_words = company_clean.split()
            
            # Check for strong suffixes/markers
            strong_suffixes = {"ltd", "limited", "inc", "corp", "corporation", "pvt", "llp", "llc", "gmbh", "co"}
            has_strong_suffix = any(w in strong_suffixes for w in company_words)
            has_org_marker = any(w in self.COMPANY_MARKERS for w in company_words)
            
            if has_strong_suffix:
                company_score = 0.9
            elif has_org_marker:
                company_score = 0.7
            else:
                company_score = 0.4
                # Capitalization check
                if company[0].isupper():
                    company_score += 0.1
                    
        # 3. Combine base score
        if company and role:
            # Rule 4: both fields are weak (generic role and weak company name)
            if (company_score <= 0.5) and is_generic:
                base_score = 0.3
            else:
                base_score = max(company_score, role_score) + 0.1
        elif company:
            # Role is missing (apply core field penalty)
            base_score = max(0.0, company_score - 0.3)
        else:
            # Company is missing (apply core field penalty)
            base_score = max(0.0, role_score - 0.3)
            
        # 4. Context bonuses
        context_bonus = 0.0
        if duration:
            context_bonus += 0.2
        if description and len(description) > 15:
            context_bonus += 0.2
        if location:
            context_bonus += 0.1
            
        final_score = base_score + context_bonus
        
        # Cap score for weak fields combinations
        if company and role and (company_score <= 0.5) and is_generic:
            final_score = min(final_score, 0.5)
            
        return round(final_score, 2)
