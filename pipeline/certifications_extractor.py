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
        "education", "experience", "work experience", "professional experience",
        "skills", "technical skills", "summary", "profile", "objective", "interests",
        "languages", "hobbies", "declaration", "achievements", "awards", 
        "positions of responsibility", "extra curricular", "extracurricular",
        "certifications", "certification", "certificates", "certificate", "courses",
        "projects", "project"
    ]

    DATE_RE = re.compile(
        r'\b(?:(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}|(?:19|20)\d{2}|'
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:19|20)\d{2})\b',
        re.I
    )

    def __init__(self, model=None):
        # Accepting model parameter for interface consistency
        self.model = model

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
            if line.lower().startswith("link:") or line.lower().startswith("http"):
                continue
                
            line_clean = re.sub(r'^[\s•\-\*⚫■★+·]+', '', line).strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
            if not line_clean or len(line_clean) < 5 or line_clean.lower() in {"certifications", "certificates", "credentials"}:
                continue
                
            org = ""
            name = line_clean
            
            known_issuers = ["udemy", "coursera", "microsoft", "google", "aws", "ibm", "linkedin", "nptel", "cisco", "oracle", "salesforce"]
            for issuer in known_issuers:
                pattern = rf"\b{issuer}\b"
                match = re.search(pattern, line_clean, re.I)
                if match:
                    org = line_clean[match.start():match.end()].title()
                    break
                    
            if not org:
                parts = re.split(r'\s*(?:,|\-|–|—|by)\s*(?=[A-Za-z0-9])', line_clean)
                if len(parts) > 1:
                    last_part = parts[-1].strip()
                    if len(last_part) < 30 and (last_part.istitle() or last_part.isupper() or any(k in last_part.lower() for k in ["university", "institute", "academy"])):
                        org = last_part
                        name = ", ".join(parts[:-1]).strip()
                        
            certs.append({
                "certification_name": name,
                "issuing_organization": org
            })
            
        return certs
