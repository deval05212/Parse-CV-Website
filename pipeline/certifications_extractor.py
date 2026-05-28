import re

class CertificationsExtractor:
    """
    Modular certifications extractor based on section parsing and layout heuristics.
    """
    
    CERT_HEADERS = [
        "certifications", "certification", "certificates", "certificate", 
        "courses and certificate", "courses and certifications", "credentials", 
        "training and certifications", "training and certification", "coursework",
        "courses", "additional credentials", "licenses & certifications", "licenses and certifications"
    ]

    NEXT_HEADERS = [
        "education", "experience", "work experience", "professional experience", "employment", "history", "employment history",
        "skills", "technical skills", "summary", "profile", "objective", "interests", "languages", "hobbies", "declaration",
        "achievements", "awards", "positions of responsibility", "extra curricular", "extracurricular", "academic achievements",
        "certifications", "certification", "certificates", "certificate", "courses", "projects", "project", "personal projects",
        "academic projects", "key projects", "recent projects", "additional details", "additional info", "additional information",
        "personal details", "personal information", "personal data", "personal profile", "personality", "references", "key skills",
        "internships", "jobs", "internships/ jobs", "internship", "professional summary", "career objective", "co-curricular activities",
        "co-curricular", "extra-curricular achievements", "academics", "academic qualification", "academic qualifications"
    ]

    ACTION_VERBS = {
        "built", "developed", "designed", "created", "implemented", "integrated", 
        "managed", "led", "used", "worked", "coordinated", "optimized", "maintained",
        "achieved", "collaborated", "assisted", "provided", "engineered", "architected",
        "reduced", "increased", "maximized", "minimized", "improved", "implemented",
        "deployed", "monitored", "configured", "setup", "set", "wrote", "written",
        "authored", "guided", "spearheaded", "headed", "supervised", "directed",
        "displayed", "enabled", "utilized", "mapped", "analyzed", "structured",
        "delivered", "practiced", "learned", "enhanced", "gained", "collaborated"
    }

    NON_TITLE_START_WORDS = {
        "using", "with", "developed", "built", "implemented", "designed", "created", 
        "integrated", "managed", "optimized", "maintained", "engineered", "architected", 
        "deployed", "from", "by", "to", "for", "on", "at", "in", "and", "or", "the", 
        "an", "a", "is", "are", "was", "were", "has", "have", "had", "as", "our", 
        "their", "this", "these", "those", "that", "which", "who", "whom", "whose", 
        "it", "its", "they", "them", "we", "us", "he", "she", "his", "her", "my", 
        "your", "soon", "heading", "developing", "building", "implementing", "achieving", 
        "collaborated", "assisted", "provided", "spearheaded", "headed", "supervised", "ongoing"
    }

    CONTINUATION_WORDS = {
        "and", "or", "with", "using", "for", "to", "in", "on", "at", "by", "of", "the", 
        "a", "an", "is", "are", "from", "implemented", "which", "that", "built", "developed",
        "engineered", "designed", "created", "integrated", "managed", "optimized"
    }

    DATE_RE = re.compile(
        r'\b(?:(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}|(?:19|20)\d{2}|'
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:19|20)\d{2})\b',
        re.I
    )

    def __init__(self, model=None):
        # Accepting model parameter for interface consistency
        self.model = model

    def deduplicate_title_words(self, title: str) -> str:
        title = title.strip()
        if not title:
            return ""
        
        words = title.split()
        if not words:
            return title
            
        n = len(words)
        if n % 2 == 0:
            half = n // 2
            if words[:half] == words[half:]:
                return " ".join(words[:half])
                
        length = len(title)
        for i in range(1, length // 2 + 1):
            if length % i == 0:
                sub = title[:i]
                if sub * (length // i) == title:
                    if len(sub.strip()) >= 3:
                        return sub.strip()
                        
        i = 0
        new_words = []
        while i < n:
            matched = False
            for sz in range(n // 2, 0, -1):
                if i + 2 * sz <= n:
                    chunk1 = words[i : i + sz]
                    chunk2 = words[i + sz : i + 2 * sz]
                    if chunk1 == chunk2:
                        new_words.extend(chunk1)
                        i += 2 * sz
                        matched = True
                        break
            if not matched:
                new_words.append(words[i])
                i += 1
                
        return " ".join(new_words)

    def is_junk_cert_title(self, text: str) -> bool:
        cleaned = text.lower().strip(" \t\n\r.,;:-|/()[]{}*•⚫■★_")
        if not cleaned:
            return True
            
        junk_words = {
            "live", "github", "link", "links", "demo", "code", "website", "project", 
            "projects", "url", "video", "repo", "repository", "view", "visit", 
            "deployment", "hosted", "site", "url", "urls", "github:https"
        }
        if cleaned in junk_words:
            return True
            
        junk_phrases = {
            "live link", "github link", "view project", "project link", "website link", 
            "code link", "demo link", "live website", "github repo", "github repository", 
            "git repo", "source code", "live demo", "view demo", "link to", "project code", 
            "hosted link", "deployment link", "play store link", "app link", "site link", 
            "web link", "live url", "github url", "github reference", "repository link", 
            "repo link", "online link", "interactive demo", "video demo", "demo url", 
            "live site", "github repos", "github homepage", "project homepage",
            "personal project", "academic project", "mini project", "major project",
            "portfolio website", "portfolio", "key project", "recent project",
            "version control"
        }
        if cleaned in junk_phrases or cleaned.startswith("github:"):
            return True
            
        if len(cleaned) <= 25:
            for word in ["link", "demo", "repo", "github", "website", "code", "url", "live", "hosted", "view", "visit"]:
                if word in cleaned:
                    return True
                    
        return False

    def strip_punctuation(self, text: str) -> str:
        cleaned = text.strip(" \t\n\r.,;:-|/&*•⚫■★")
        
        while cleaned.endswith(")") and cleaned.count(")") > cleaned.count("("):
            cleaned = cleaned[:-1].strip()
        while cleaned.startswith("(") and cleaned.count("(") > cleaned.count(")"):
            cleaned = cleaned[1:].strip()
        while cleaned.endswith("]") and cleaned.count("]") > cleaned.count("["):
            cleaned = cleaned[:-1].strip()
        while cleaned.startswith("[") and cleaned.count("[") > cleaned.count("]"):
            cleaned = cleaned[1:].strip()
        while cleaned.endswith("}") and cleaned.count("}") > cleaned.count("{"):
            cleaned = cleaned[:-1].strip()
        while cleaned.startswith("{") and cleaned.count("{") > cleaned.count("}"):
            cleaned = cleaned[1:].strip()
            
        if cleaned.startswith("(") and cleaned.endswith(")") and cleaned.count("(") == 1 and cleaned.count(")") == 1:
            cleaned = cleaned[1:-1].strip()
        if cleaned.startswith("[") and cleaned.endswith("]") and cleaned.count("[") == 1 and cleaned.count("]") == 1:
            cleaned = cleaned[1:-1].strip()
            
        return cleaned.strip(" \t\n\r.,;:-|/&*•⚫■★")

    def balance_parens(self, text: str) -> str:
        open_p = text.count("(")
        close_p = text.count(")")
        if open_p > close_p:
            text = text + ")" * (open_p - close_p)
        elif close_p > open_p:
            for _ in range(close_p - open_p):
                if text.endswith(")"):
                    text = text[:-1].strip()
                else:
                    text = "(" + text
                    
        open_b = text.count("[")
        close_b = text.count("]")
        if open_b > close_b:
            text = text + "]" * (open_b - close_b)
        elif close_b > open_b:
            for _ in range(close_b - open_b):
                if text.endswith("]"):
                    text = text[:-1].strip()
                else:
                    text = "[" + text
                    
        return text

    def _isolate_section(self, text: str) -> str:
        lines = text.split("\n")
        start_idx = -1
        for i, line in enumerate(lines):
            clean_line = re.sub(r'^[\s•\-\*⚫■★]+', '', line.strip().lower())
            clean_line = re.sub(r'[:\-.]+$', '', clean_line).strip()
            clean_line = re.sub(r'\s+', ' ', clean_line)
            if clean_line in self.CERT_HEADERS:
                start_idx = i + 1
                break
                
        if start_idx == -1:
            for i, line in enumerate(lines):
                clean_line = line.strip().lower()
                if any(h == clean_line for h in self.CERT_HEADERS):
                    start_idx = i + 1
                    break
                if any(f" {h} " in f" {clean_line} " for h in self.CERT_HEADERS) and len(clean_line) < 40:
                    if not clean_line.endswith("."):
                        start_idx = i + 1
                        break
                    
        if start_idx == -1:
            return ""
            
        end_idx = len(lines)
        for i in range(start_idx, len(lines)):
            clean_line = re.sub(r'^[\s•\-\*⚫■★]+', '', lines[i].strip().lower())
            clean_line = re.sub(r'[:\-.]+$', '', clean_line).strip()
            clean_line = re.sub(r'\s+', ' ', clean_line)
            # Stop ONLY if the line is exactly one of the NEXT_HEADERS (excluding the current header)
            if clean_line in self.NEXT_HEADERS and clean_line not in self.CERT_HEADERS:
                end_idx = i
                break
                
        return "\n".join(lines[start_idx:end_idx]).strip()

    def extract(self, text: str) -> list[dict]:
        section_text = self._isolate_section(text)
        if not section_text:
            return []
            
        lines = [l.strip() for l in section_text.split("\n") if l.strip()]
        certs = []
        
        for line in lines:
            if self.DATE_RE.match(line) and len(line) < 15:
                continue
            if line.lower().startswith("link:") or line.lower().startswith("http") or line.lower().startswith("github:"):
                continue
                
            line_clean = re.sub(r'^[\s•\-\*⚫■★+·]+', '', line).strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
            if not line_clean or len(line_clean) < 5 or line_clean.lower() in {"certifications", "certificates", "credentials"}:
                continue
                
            # Perform quality validation checks
            starts_with_cap = line_clean[0].isupper() or line_clean[0].isdigit()
            if not starts_with_cap:
                continue
                
            if line_clean.endswith((".", ",", ";", "!")):
                continue
                
            # Filter out locations, postal/zip codes, and status markers
            if re.search(r'\b\d{5,6}\b', line_clean):
                continue
            
            line_lower = line_clean.lower()
            if any(loc in line_lower for loc in ["pune", "maharashtra", "gujarat", "surat", "mumbai", "india", "ongoing", "present"]):
                continue
                
            # Filter out job roles/experience/project terms that lack certification indicators
            role_keywords = ["developer", "engineer", "intern", "manager", "lead", "executive", "specialist", "project", "projects", "analyst"]
            cert_indicators = ["certified", "certification", "certificate", "cert", "course", "bootcamp", "training", "exam", "passed", "udemy", "coursera", "nptel", "ibm", "google", "microsoft", "aws", "oracle", "cisco", "salesforce"]
            if any(role in line_lower for role in role_keywords):
                if not any(indicator in line_lower for indicator in cert_indicators):
                    continue
                    
            first_word = line_clean.split()[0].lower().strip(".,;:()") if line_clean.split() else ""
            if first_word in self.ACTION_VERBS or first_word in self.NON_TITLE_START_WORDS:
                continue
                
            last_word_in_line = line_clean.split()[-1].lower().strip(".:;!?()[]{}") if line_clean.split() else ""
            if last_word_in_line in self.CONTINUATION_WORDS:
                continue
                
            if self.is_junk_cert_title(line_clean):
                continue
                
            name = self.deduplicate_title_words(line_clean)
            if self.is_junk_cert_title(name) or len(name) < 5:
                continue
                
            org = ""
            
            known_issuers = ["udemy", "coursera", "microsoft", "google", "aws", "ibm", "linkedin", "nptel", "cisco", "oracle", "salesforce"]
            for issuer in known_issuers:
                pattern = rf"\b{issuer}\b"
                match = re.search(pattern, name, re.I)
                if match:
                    org = name[match.start():match.end()].title()
                    break
                    
            if not org:
                parts = re.split(r'\s*(?:,|\-|–|—|by)\s*(?=[A-Za-z0-9])', name)
                if len(parts) > 1:
                    last_part = parts[-1].strip()
                    if len(last_part) < 30 and (last_part.istitle() or last_part.isupper() or any(k in last_part.lower() for k in ["university", "institute", "academy"])):
                        org = last_part
                        name = ", ".join(parts[:-1]).strip()
                        
            name = self.balance_parens(self.strip_punctuation(name))
            if not name or len(name) < 5:
                continue
                
            certs.append({
                "certification_name": name,
                "issuing_organization": org
            })
            
        return certs
