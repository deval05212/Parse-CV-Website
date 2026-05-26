import re
import logging
from typing import List, Set

log = logging.getLogger(__name__)

# Multi-word skills to prevent split errors (greedy matching)
KNOWN_MULTI_WORDS = [
    "visual studio code", "visual studio", "google colab", "google cloud platform",
    "google cloud", "microsoft azure", "azure ai engineer", "fabric data engineer",
    "data engineer", "ai engineer", "retrieval-augmented generation", "machine learning",
    "data science", "computer vision", "data analysis", "data structure", "data structures",
    "database management", "project management", "power point", "ms office", "ms word",
    "ms excel", "software engineering", "web development", "deep learning", "natural language",
    "ethical hacking", "red teaming", "penetration testing", "sql injection", "vuln assessment",
    "information technology", "java script", "cyber security", "cloud computing",
    "active directory", "power bi", "rest api", "rest apis", "restful api", "restful apis",
    "agile methodologies", "scrum master", "unit testing", "integration testing", "next js",
    "node js", "react js", "vue js", "three js", "spring boot", "spring framework",
    "react native", "mongodb atlas", "google play", "play console", "firebase console",
    
    "amazon web", "web services", "lead generation", "client relation", "client relations",
    "client follow-up", "staff augmentation", "attendance and payroll", "performance management",
    "policy implementation", "market research", "digital marketing", "social media",
    "communication skills", "team collaboration", "problem solving", "time management",
    "written communication", "verbal communication", "interpersonal skills", "technical support",
    "analytical skills", "adaptability & flexibility", "critical thinking", "team work"
]

PROJECT_HEADERS = {
    "projects", "project", "personal projects", "academic projects", "college projects",
    "key projects", "mini projects", "major projects", "recent projects", "project work",
    "projects worked on"
}

SKILL_SECTION_NAMES = {
    "skills", "technical skills", "core skills", "key skills", "professional skills",
    "skills & technologies", "skills and technologies", "technologies", "tools",
    "coursework", "areas of expertise", "core competencies", "skills / tools",
    "skills/tools", "professional expertise", "technical profile", "key expertise",
    "it skills", "software skills", "programming skills", "relevant skills",
    "computer skills", "personal skills", "soft skills", "additional skills",
    "skills and tools", "skills & tools"
}

SECTION_HEADERS = {
    "summary", "experience", "work experience", "professional experience",
    "skills", "technical skills", "education", "qualifications",
    "projects", "certificates", "certifications",
    "objective", "profile", "interests", "achievements", "strengths",
    "education history", "academic details", "declaration", "personal profile",
    "strengths & interests", "extra curricular activities", "extra-curricular activities",
    "hobbies", "activities", "awards", "co-curricular activities"
}
SECTION_HEADERS.update(PROJECT_HEADERS)
SECTION_HEADERS.update(SKILL_SECTION_NAMES)

SKILLS_STOP_HEADERS = {
    "experience", "work experience", "professional experience", "education",
    "qualifications", "projects", "certificates", "certifications",
    "objective", "profile", "interests", "achievements"
}

# Whitelist bypass for high-value professional and technical skills
ALLOWED_SKILLS_BYPASS = {
    # Sales & Marketing / Business
    "sales", "marketing", "strategy", "client acquisition", "relationship management",
    "business development", "lead generation", "cross-selling", "upselling", "negotiation",
    "b2b sales", "b2c sales", "cold calling", "field sales", "financial product advisory",
    "customer acquisition", "client relationship management", "sales strategy", "marketing strategy",
    "sales and marketing strategy", "b2b and b2c sales", "client acquisition and relationship management",
    "cross-selling and upselling", "financial product advisory", "lead generation and conversion",
    "target achievement and business development", "communication and negotiation",
    "customer service", "customer relations", "client relations", "portfolio management",
    "onboarding", "retention", "bde", "business banking", "casa", "assets", "insurance sales",
    "general insurance", "life insurance", "health insurance",
    
    # Soft Skills & Common Professional Skills
    "problem solving", "problem-solving", "team work", "teamwork", "critical thinking",
    "time management", "communication skills", "interpersonal skills", "leadership",
    "adaptability", "flexibility", "active listening", "presentation skills",
    
    # Technical & Cybersecurity
    "penetration testing", "vulnerability assessment", "vulnerability assessments",
    "burp suite", "wireshark", "kali linux", "nmap", "metasploit", "sql injection",
    "xss", "csrf", "idor", "html injection", "ethical hacking", "red teaming",
    "cyber security", "cybersecurity", "information security", "network security",
    
    # Systems & Networking
    "iis", "ssl", "dns", "load balancer", "active directory",
    
    # Embedded & Hardware
    "cad", "autocad", "solidworks", "arduino", "arduino ide", "esp-32", "esp32",
    "3d printing", "sensors", "robotics", "iot", "iot devices", "wireless bluetooth module"
}

# Curated skills to scan case-insensitively across the entire text
SCAN_KEYWORDS = {
    # Programming Languages
    "python", "javascript", "typescript", "c++", "c#", "java", "php", "ruby", "rails",
    "rust", "kotlin", "swift", "dart", "go", "scala", "c/c++", "pl/sql",
    
    # Frameworks & Libraries
    "react", "react.js", "reactjs", "angular", "angularjs", "vue", "vue.js", "vuejs", "vue3",
    "next.js", "nextjs", "node.js", "nodejs", "express.js", "expressjs", "django", "flask",
    "fastapi", "spring boot", "laravel", "codeigniter", "jquery", "bootstrap", "tailwind css",
    "tailwindcss", "material-ui", "mui", "shadcn/ui", "redux", "pinia", "rxjs",
    
    # Databases
    "mysql", "postgresql", "postgres", "sqlite", "oracle", "mssql", "sql server", "mongodb",
    "redis", "cassandra", "mariadb", "cosmosdb", "dynamodb", "firebase", "firestore", "supabase",
    
    # Cloud, DevOps & Platforms
    "aws", "amazon web services", "azure", "gcp", "google cloud", "google cloud platform",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "github actions",
    "gitlab ci", "nginx", "apache", "iis", "ssl", "dns", "load balancer", "route 53",
    "aws lambda", "s3", "ec2", "ecs", "eks",
    
    # Development Tools
    "git", "github", "gitlab", "bitbucket", "jira", "confluence", "trello", "postman",
    "figma", "canva", "vs code", "visual studio", "visual studio code", "eclipse",
    "intellij", "pycharm", "android studio", "xcode", "jupyter", "power bi", "tableau",
    "google analytics", "ms office", "excel", "powerpoint",
    
    # Cybersecurity & Networking
    "burp suite", "wireshark", "kali linux", "nmap", "metasploit", "nessus", "owasp",
    "penetration testing", "ethical hacking", "red teaming", "vulnerability assessment",
    "vulnerability assessments", "sql injection", "xss", "csrf", "idor", "html injection",
    "cyber security", "cybersecurity",
    
    # Embedded, IoT & Hardware
    "arduino", "raspberry pi", "esp32", "esp-32", "stm32", "microcontrollers", "sensors",
    "robotics", "cad", "autocad", "solidworks", "3d printing", "iot", "iot devices",
    "wireless bluetooth module",
    
    # Soft & Professional Skills
    "problem solving", "team work", "teamwork", "critical thinking", "time management",
    "communication skills", "interpersonal skills", "leadership", "adaptability",
    
    # Languages
    "english", "hindi", "gujarati", "german", "french", "spanish", "marathi", "gujrati",
    "bengali", "punjabi", "sindhi", "marwari", "kannada", "telugu", "tamil"
}

BLACKLISTED_SKILLS = {
    "+", "more", "udemy", "dp", "fabric", "data", "engineer", "associate", "developer",
    "libraries", "code", "apis", "platforms", "tools", "languages", "backend", "frontend",
    "generation", "retrieval-augmented", "learning", "science", "vision", "analysis",
    "structure", "structures", "management", "studio", "office", "word", "excel",
    "powerpoint", "cloud", "security", "computing", "directory", "master", "testing",
    "boot", "framework", "native", "atlas", "play", "console", "services", "relation",
    "relations", "follow-up", "augmentation", "payroll", "implementation", "research",
    "marketing", "media", "collaboration", "solving", "support", "skills", "thinking",
    "work", "certification", "certifications", "certificate", "courses", "course",
    "university", "college", "school", "degree", "hobbies", "interests", "personal",
    "profile", "summary", "objective", "references", "declaration", "projects",
    "experience", "employment", "activities", "achievements", "awards", "timeline",
    "duration", "location", "phone", "email", "website", "reference", "salary",
    "ctc", "etc", "etc.", "various", "different", "multiple", "and more", "known",
    "technical", "key", "additional", "other", "core", "competencies", "expertise",
    "areas", "job", "professional", "subject", "like", "software", "personal skills",
    "frontend libraries", "tools / platforms", "platforms", "libraries", "coursework", 
    "technologies", "technical skills", "skills", "operating systems", "database", 
    "databases", "framework", "technology", "personal", "languages known",
    "microsoft", "administration", "operations", "engagement", "tasks", "compliance",
    "growth", "acquisition", "sales", "strategy", "solution", "solutions", "joined",
    "am", "currently", "development", "developer", "engineering", "design", "designer",
    "deadlines", "deadline", "written", "verbal", "communication", "languages",
    "strength", "strengths", "achievement", "achievements", "award", "awards",
    "punctual", "responsible", "helpful", "month", "employee", "academic", "excellence",
    "post", "graduated", "history", "qualification", "qualifications", "profile",
    "cv", "resume", "curriculum", "vitae", "details", "personal details", "hobbies",
    
    # Newly added noise and weak terms
    "basic", "advanced", "unit", "requirements", "calls", "team", "softwares", "contact",
    "basics", "learning", "hobby", "hobbies", "interest", "interests", "hometown",
    
    # Newly added location/city noise
    "surat", "gujarat", "india", "mumbai", "ahmedabad", "vadodara", "pune", "bhopal",
    "anand", "nadiad", "rajkot", "baroda", "gandhinagar", "delhi", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "germany", "france", "spain", "usa", "uk", "london",
    
    # Category headers/noise to filter out
    "testing/methodology", "tools/platforms", "tools & platforms", "tools / platforms", 
    "soft skills", "programming languages", "frameworks / libraries", "frameworks and libraries", 
    "frameworks & libraries", "developer tools", "apis and data handling", "apis & data handling", 
    "version control", "devops and deployment", "devops & deployment", "build tools", 
    "core competencies",
    
    # Extra noise words and OCR artifacts to blacklist
    "methodology", "specification", "specifications", "posting", "retention", 
    "basic interview", "interview", "bank departments", "department", "present", 
    "current", "organisation", "sourcing tools", "cricket", "reading", "music", 
    "traveling", "travelling", "sports", "edit prompt", "copy reply", "like response", 
    "response", "reply", "prompt", "na ve", "bilingual", "bilingual pro ciency", 
    "pro ciency", "proficiency", "professional proficiency", "link", "links", "portfolio link", 
    "portfolio-work", "node-id"
}

PREFIX_WORDS_TO_STRIP = {
    "languages", "backend", "frontend", "devops", "others", "tools", "caching", 
    "platforms", "subjects", "subject", "roles", "role", "additional", "technical", 
    "core", "technologies"
}

TECH_KEYWORDS = {
    "python", "numpy", "pandas", "matplotlib", "scikit-learn", "opencv", "easyocr", "yolo",
    "html", "css", "javascript", "js", "php", "mysql", "c++", "c", "java", "vb.net", "oracle",
    "sqlite", "mongodb", "git", "github", "docker", "aws", "sql", "react", "angular", "nodejs",
    "express", "django", "flask", "redis", "postgres", "kubernetes", "jenkins", "jira", "figma",
    "postman", "excel", "word", "powerpoint", "bash", "shell", "typescript", "bootstrap",
    "tailwind", "go", "rust", "kotlin", "swift", "flutter", "dart", "spring", "dotnet", "net",
    "asp.net", "hibernate", "sequelize", "mongoose", "socket.io", "pm2", "trello", "webpack",
    "powerbi", "tableau", "c#", "azure", "gcp", "docker-compose", "bitbucket", "gitlab",
    "postgressql", "mariadb", "firebase", "redux", "nextjs", "vuejs", "sass", "less", "npm",
    "yarn", "pnpm", "vite", "babel", "eslint", "prettier", "jest", "cypress",
    "selenium", "postgre", "graphql", "apollo", "prisma", "fastapi", "streamlit",
    "opencv-python", "keras", "nltk", "spacy", "huggingface", "transformers", "pytorch",
    "tensorflow", "scipy", "seaborn", "plotly", "outlook", "confluence", "asana", "slack",
    "zoom", "teams", "skype", "english", "hindi", "gujarati", "german", "french", "spanish",
    "marathi", "gujrati", "bengali", "punjabi", "sindhi", "marwari", "kannada", "telugu", "tamil"
}

NORM_MAP = {
    "react": "React.js",
    "reactjs": "React.js",
    "react.js": "React.js",
    "react js": "React.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "next js": "Next.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "vue js": "Vue.js",
    "angular": "Angular",
    "angularjs": "AngularJS",
    "angular.js": "AngularJS",
    
    "javascript": "JavaScript",
    "java script": "JavaScript",
    "js": "JavaScript",
    
    "typescript": "TypeScript",
    "type script": "TypeScript",
    "ts": "TypeScript",
    
    "python": "Python",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "scikit-learn": "Scikit-Learn",
    "scikit learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "matplotlib": "Matplotlib",
    "opencv": "OpenCV",
    "opencv-python": "OpenCV",
    "easyocr": "EasyOCR",
    "yolo": "YOLO",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "sass": "Sass",
    "less": "Less",
    "bootstrap": "Bootstrap",
    "bootstrap css": "Bootstrap",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgre": "PostgreSQL",
    "postgressql": "PostgreSQL",
    "mongodb": "MongoDB",
    "mongo db": "MongoDB",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "mariadb": "MariaDB",
    "redis": "Redis",
    "firebase": "Firebase",
    
    "git": "Git",
    "github": "GitHub",
    "git hub": "GitHub",
    "github desktop": "GitHub",
    "gitlab": "GitLab",
    "git lab": "GitLab",
    "bitbucket": "Bitbucket",
    
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "jenkins": "Jenkins",
    
    "fastapi": "FastAPI",
    "fast api": "FastAPI",
    "python fast api": "FastAPI",
    
    "net": ".NET",
    "dotnet": ".NET",
    ".net": ".NET",
    "net core": ".NET Core",
    "dotnet core": ".NET Core",
    ".net core": ".NET Core",
    "net api": ".NET API",
    ".net api": ".NET API",
    "asp.net": "ASP.NET",
    "asp net": "ASP.NET",
    
    "c#": "C#",
    "csharp": "C#",
    "c++": "C++",
    "cplusplus": "C++",
    "c/c++": "C/C++",
    
    "redux": "Redux",
    "redux toolkit": "Redux",
    
    "jupyter": "Jupyter",
    "jupyter notebook": "Jupyter",
    "jupyter notebooks": "Jupyter",
    
    "problem solving": "Problem Solving",
    "problem-solving": "Problem Solving",
    "problem-solving skills": "Problem Solving",
    "strong problem-solving skills": "Problem Solving",
    
    "adaptibily": "Adaptability",
    "adaptability": "Adaptability",
    
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "express js": "Express.js",
    
    "rest api": "REST API",
    "rest apis": "REST API",
    "restful api": "REST API",
    "restful apis": "REST API",
    
    "powerbi": "Power BI",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "figma": "Figma",
    "postman": "Postman",
    "excel": "Excel",
    "ms excel": "Excel",
    "word": "Word",
    "ms word": "Word",
    "powerpoint": "PowerPoint",
    "ms powerpoint": "PowerPoint",
    
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "natural language processing": "NLP",
    "nlp": "NLP",
    "data science": "Data Science",
    "data structures": "Data Structures",
    "data structure": "Data Structures",
    "data structures and algorithms": "Data Structures & Algorithms",
    "dsa": "Data Structures & Algorithms",
    "dbms": "DBMS",
    "database management system": "DBMS",
    "database management systems": "DBMS",
    
    "gujrati": "Gujarati",
    "marathi": "Marathi",
    "sindhi": "Sindhi",
    "punjabi": "Punjabi",
    "bengali": "Bengali",
    "kannada": "Kannada",
    "telugu": "Telugu",
    "tamil": "Tamil",
}

class SkillsExtractor:
    """
    Modular hybrid skills extractor.
    Combines GLiNER predictions and section parsing logic from extract_skills.py.
    """

    def __init__(self, model):
        self.model = model

    def _clean_category_prefix(self, name: str) -> str:
        """Strip leading category header words and symbols (e.g. 'Languages C' -> 'C')."""
        if not name:
            return ""
        words = name.split()
        if not words:
            return name
            
        changed = True
        while changed and len(words) > 1:
            first_word = words[0].lower().strip(".,;:()/-&|•")
            # If the first word is empty or is in PREFIX_WORDS_TO_STRIP
            if not first_word or first_word in PREFIX_WORDS_TO_STRIP:
                words.pop(0)
            else:
                changed = False
                
        cleaned = " ".join(words).strip(" \t\n\r.,;:-|/()[]{}*•⚫■★&")
        return cleaned

    def normalize_skill(self, name: str) -> str:
        """Normalize skill names to a canonical standard representation."""
        if not name:
            return ""
        cleaned_prefix = self._clean_category_prefix(name)
        cleaned = self._clean_skill(cleaned_prefix)
        if not cleaned:
            return ""
        
        # Check in our canonical NORM_MAP
        key = cleaned.lower()
        if key in NORM_MAP:
            return NORM_MAP[key]
            
        # For other names, if lowercase, title case them.
        # Otherwise preserve their casing (like OpenCV, JQuery, SQLite, etc.)
        if cleaned.islower():
            # Title case each word, but keep words like 'and', 'or', 'of', 'in' lowercase unless they start the name
            words = cleaned.split()
            title_words = []
            for idx, w in enumerate(words):
                if idx > 0 and w in {"and", "or", "of", "in", "with", "to", "for"}:
                    title_words.append(w)
                else:
                    title_words.append(w.capitalize())
            return " ".join(title_words)
            
        return cleaned

    def extract(self, text: str) -> List[str]:
        """Hybrid skills extraction combining GLiNER NER and Section parsing."""
        # 1. Strip projects section to avoid extracting project names or project descriptions in GLiNER
        cleaned_text = self._remove_sections(text, PROJECT_HEADERS)

        # 2. Run GLiNER prediction on clean text
        try:
            entities = self.model.predict_entities(cleaned_text, ["SKILLS"], threshold=0.5)
            gliner_skills = [ent["text"].strip() for ent in entities if ent["label"] == "SKILLS"]
        except Exception as e:
            log.exception(f"GLiNER prediction failed in SkillsExtractor: {e}")
            gliner_skills = []

        # 3. Section-Aware Heuristic Parser
        skills_lines = self._get_section_lines(text, *SKILL_SECTION_NAMES)
        parsed_skills = []
        for line in skills_lines:
            stripped = line.strip()
            if not stripped:
                continue
            low_stripped = stripped.lower().rstrip(":")
            if any(low_stripped.startswith(h) for h in SKILLS_STOP_HEADERS):
                # If there's a colon followed by content, it's likely a category prefix (e.g. "Languages: ...")
                # rather than a new section header.
                if ":" in stripped and stripped.split(":", 1)[1].strip():
                    pass
                else:
                    break
                
            if ":" in stripped:
                parts = stripped.split(":", 1)
                category = parts[0].strip()
                content = parts[1].strip()
                skills_line = content if len(category) < 35 else stripped
            else:
                skills_line = stripped
                
            for item in self._split_skills_line(skills_line):
                normalized = self.normalize_skill(item)
                if normalized and len(normalized) < 50 and self._is_valid_skill(normalized):
                    parsed_skills.append(normalized)

        # 4. Parse specific Technology/Tools/Environment lines in the original text (including projects/experience sections)
        tech_line_skills = []
        tech_label_pattern = re.compile(
            r"(?i)\b(technology|technologies|tools|environment|tech\s*stack|key\s*tools|dev\s*tools|platforms|languages)\s*(?:used)?\s*[:\-–—]"
        )
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            match = tech_label_pattern.search(stripped)
            if match:
                content = stripped[match.end():].strip()
                if content:
                    for item in self._split_skills_line(content):
                        normalized = self.normalize_skill(item)
                        if normalized and len(normalized) < 50 and self._is_valid_skill(normalized):
                            tech_line_skills.append(normalized)

        # 5. Whole-Text Keyword Scanner
        scanned_skills = []
        for keyword in SCAN_KEYWORDS:
            # Custom boundaries to support special chars like +, #, ., /
            pattern = re.compile(rf"(?<![a-zA-Z0-9_]){re.escape(keyword)}(?![a-zA-Z0-9_])", re.IGNORECASE)
            if pattern.search(text):
                normalized = self.normalize_skill(keyword)
                if normalized and self._is_valid_skill(normalized):
                    scanned_skills.append(normalized)

        # 6. Merge & Deduplicate
        seen = set()
        final_skills = []
        for s in gliner_skills:
            normalized = self.normalize_skill(s)
            if normalized and normalized.lower() not in seen and self._is_valid_skill(normalized):
                seen.add(normalized.lower())
                final_skills.append(normalized)
                
        for s in parsed_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                final_skills.append(s)

        for s in tech_line_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                final_skills.append(s)

        for s in scanned_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                final_skills.append(s)
                
        return final_skills

    def _clean_parentheses(self, text: str) -> str:
        """Balance unmatched parentheses or brackets."""
        if text.count("(") != text.count(")"):
            text = text.replace("(", "").replace(")", "")
        if text.count("[") != text.count("]"):
            text = text.replace("[", "").replace("]", "")
        return text.strip()

    def _clean_skill(self, name: str) -> str:
        """Standardize string formatting and strip outer noise characters."""
        if not name:
            return ""
        name = re.sub(r"^[\s()\[\]{}\"\'\\/:\-\*•·.]+|[\s()\[\]{}\"\'\\/:\-\*•·.]+$", "", name)
        name = " ".join(name.split())
        return self._clean_parentheses(name)

    def _is_valid_skill(self, name: str) -> bool:
        """Validate skill candidate to filter out non-skill sentences, dates, pronouns, or noise."""
        name_lower = name.lower()
        words = name_lower.split()
        if not words:
            return False
            
        # Whitelist bypass for trusted technical/professional skills
        if name_lower in ALLOWED_SKILLS_BYPASS:
            return True
            
        # Block blacklisted items
        if name_lower in BLACKLISTED_SKILLS:
            return False
        if len(words) == 1 and words[0] in BLACKLISTED_SKILLS:
            return False
            
        # Block company and institution names
        corp_indicators = {
            "infotech", "solutions", "technologies", "pvt", "ltd", "llp", "inc", "corp", 
            "corporation", "university", "college", "school", "foundation", "institute", 
            "institutes", "academy"
        }
        if any(ind in name_lower for ind in corp_indicators):
            return False
            
        # 1. Length and Word count check
        if len(name) > 40 or len(words) > 4:
            allowed_long_skills = {
                "data structures and algorithms",
                "data structures & algorithms",
                "artificial intelligence & machine learning",
                "continuous integration / continuous deployment",
                "natural language processing",
                "software development life cycle",
                "amazon web services",
                "google cloud platform",
                "microsoft azure"
            }
            if not any(allowed in name_lower for allowed in allowed_long_skills):
                return False
                
        # 2. Filter out email/phone/urls/dates/years/pronouns
        if "@" in name or "http" in name or "www." in name:
            return False
        # Filter out URL query params, broken links or tokens (e.g. t=VvX8VgraHvDfBvVk-1, node-id=0-6)
        if "?" in name_lower or "=" in name_lower:
            return False
        if "+" in name:
            if len(re.findall(r"\d", name)) >= 3:
                return False
        # Filter out integers or float numbers/CGPAs (e.g. 7.36, 8.08, 2024)
        if any(re.match(r"^\d+(\.\d+)?$", w) for w in words):
            return False
            
        # Regex to block OCR-damaged years (e.g. 2o17, 2o23, 2024)
        if re.search(r"\b[12][09oO][0-9oO]{2}\b", name_lower):
            return False
        if re.search(r"\b\d{4}\b", name):
            return False
        if re.search(r"\b(i|me|my|we|us|our|you|he|she|they|them|their)\b", name_lower):
            return False
        if re.search(r"\b(more|and more)\b", name_lower):
            return False
            
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        if any(re.search(rf"\b{m}\b", name_lower) for m in months):
            return False
            
        # 3. Filter out sentence fragments / action descriptions
        gerund_words = {"implementing", "integrating", "enabling", "designing", "developing", "managing", "writing", "handling", "improving", "solving", "assisting", "ensuring", "collaborating", "optimizing", "delivering", "building", "creating", "working", "contributing", "achieving", "managing", "addressing", "directing", "using", "performing", "learning", "listening", "teaching"}
        action_verbs = {"develop", "create", "build", "manage", "ensure", "perform", "integrate", "deliver", "provide", "work", "contribute", "design", "solve", "improve", "optimize", "maintain", "enhance", "writing", "identifying", "fixing", "performing", "testing", "deploying"}
        
        known_gerund_skills = {"machine learning", "deep learning", "problem solving", "web development", "software development", "database management", "cloud computing", "digital marketing", "project management", "data mining", "ethical hacking", "penetration testing", "red teaming", "system exploitation", "vulnerability assessment", "team work", "teamwork"}
        
        has_action = False
        for w in words:
            w_clean = w.strip(".,:-")
            if w_clean in gerund_words or w_clean in action_verbs:
                has_action = True
                break
                
        if has_action:
            if not any(known in name_lower for known in known_gerund_skills):
                return False
                
        # 4. Filter out typical noise words
        noise_patterns = [
            r"\b(roles|responsibilities|experience|employment|projects|summary|details|declaration|interests|hobbies|personal|about|activities|achievements|certifications|certificates|courses|awards)\b",
            r"\b(client|user|device|browser|timeline|duration|location|phone|email|website|reference|salary|ctc)\b",
            r"\b(technologies like|skills in|experience in|knowledge of|proficient in|understanding of|familiar with|working with|hands-on|strong background in|ability to)\b",
            r"\b(clean code|coding standards|best practices|standards|methodologies)\b",
            r"\b(real-world|real-time|high-quality|user-centric|scalable|modular|secure)\b",
            r"\b(various|different|multiple|etc|and more|etc\.)\b"
        ]
        for pattern in noise_patterns:
            if re.search(pattern, name_lower):
                valid_exceptions = {
                    "user experience", "user interface", "ux/ui", "ui/ux", "personal finance", 
                    "client relations", "thunder client", "rest client", "client-side", "client side"
                }
                if not any(exc in name_lower for exc in valid_exceptions):
                    return False
                    
        # 5. Avoid stray grammar particles
        if words[0] in {"and", "or", "to", "for", "with", "in", "on", "at", "by", "from", "the", "a", "an", "of", "about"}:
            return False
        if words[-1] in {"and", "or", "to", "for", "with", "in", "on", "at", "by", "from", "the", "a", "an", "of", "about"}:
            return False
            
        return True

    def _split_skills_line(self, line: str) -> List[str]:
        """Split line containing comma or space separated skills."""
        # Remove any URLs from the line first to prevent them from splitting into garbage segments
        line = re.sub(r'https?://\S+', ' ', line, flags=re.IGNORECASE)
        line = re.sub(r'www\.\S+', ' ', line, flags=re.IGNORECASE)
        
        # 1. Parse parenthetical parts first
        items_to_process = []
        matches = re.findall(r"\(([^)]+)\)", line)
        cleaned_line = line
        for m in matches:
            items_to_process.append(m)
            cleaned_line = cleaned_line.replace(f"({m})", " ")
            
        # Protect slashed words
        slashed_placeholders = {}
        PROTECTED_SLASH_WORDS = ["c/c++", "pl/sql", "tcp/ip", "ci/cd", "ui/ux", "ux/ui", "shadcn/ui"]
        for idx, term in enumerate(PROTECTED_SLASH_WORDS):
            placeholder = f"__SLASH_{idx}__"
            while True:
                start = cleaned_line.lower().find(term)
                if start == -1:
                    break
                orig_text = cleaned_line[start:start+len(term)]
                slashed_placeholders[placeholder] = orig_text
                cleaned_line = cleaned_line[:start] + placeholder + cleaned_line[start+len(term):]
                
        items_to_process.append(cleaned_line)
        
        final_segments = []
        for item in items_to_process:
            # Split by comma, semicolon, pipe, bullets, conjunctions, and slash
            for part in re.split(r"[,;|•/]|\b(?:and|or|&)\b", item, flags=re.IGNORECASE):
                part = part.strip()
                if part:
                    # Restore slashed placeholders in the segment
                    for ph, orig in slashed_placeholders.items():
                        part = part.replace(ph, orig)
                    final_segments.append(part)
                    
        # 2. Process each segment
        result = []
        for seg in final_segments:
            # Protect multi-words
            placeholders = {}
            temp_line = seg
            sorted_multi = sorted(KNOWN_MULTI_WORDS, key=len, reverse=True)
            for i, term in enumerate(sorted_multi):
                pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
                matches = pattern.findall(temp_line)
                if matches:
                    placeholders[f"__MULTI_{i}__"] = matches[0]
                    temp_line = pattern.sub(f" __MULTI_{i}__ ", temp_line)
                    
            words = temp_line.split()
            if len(words) > 1:
                # Check if we should split by space: 
                # Only split if all split parts (excluding multi-word placeholders) are known tech keywords
                should_split = True
                for w in words:
                    w_clean = self._clean_skill(w).lower()
                    if not w_clean:
                        continue
                    if w_clean in placeholders:
                        continue
                    if w_clean not in TECH_KEYWORDS:
                        should_split = False
                        break
                
                if should_split:
                    for w in words:
                        w_clean = w.strip()
                        if w_clean:
                            if w_clean in placeholders:
                                result.append(placeholders[w_clean])
                            else:
                                result.append(w_clean)
                else:
                    # Restore placeholders in the original segment and keep as a single term
                    restored = seg
                    for ph, orig in placeholders.items():
                        restored = restored.replace(ph, orig)
                    result.append(restored)
            else:
                # Restore placeholders
                restored = seg
                for ph, orig in placeholders.items():
                    restored = restored.replace(ph, orig)
                result.append(restored)
                
        return result

    def _get_section_lines(self, full_text: str, *names: str) -> List[str]:
        """Extract all text lines belonging to matching sections."""
        lines = full_text.split("\n")
        inside = False
        raw_result = []
        name_set = {n.lower() for n in names}
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            low_clean = stripped.lower().rstrip(":")
            if not inside:
                if low_clean in name_set:
                    inside = True
                    continue
            else:
                if low_clean in SECTION_HEADERS and low_clean not in name_set:
                    break
                raw_result.append(stripped)
                
        # Merge wrapped lines (e.g. ending with connective words or if next line starts with lowercase)
        result = []
        i = 0
        raw_result_len = len(raw_result)
        while i < raw_result_len:
            curr_line = raw_result[i]
            while i < raw_result_len - 1:
                next_line = raw_result[i + 1]
                words = curr_line.split()
                if not words:
                    break
                last_word = words[-1].lower().strip(".,;:()")
                
                # Check if it ends with a separator/conjunction/preposition
                ends_with_connective = last_word in {"and", "or", "with", "to", "for", "in", "of", "on", "at", "&", ",", "/", "-"}
                
                # Check if the next line starts with a lowercase letter and current line has no ending punctuation
                next_starts_lowercase = next_line and next_line[0].islower() and not curr_line.endswith((".", ";", ":"))
                
                if ends_with_connective or next_starts_lowercase:
                    i += 1
                    curr_line = curr_line + " " + next_line
                else:
                    break
            result.append(curr_line)
            i += 1
            
        return result

    def _remove_sections(self, full_text: str, names_to_remove: Set[str]) -> str:
        """Remove target sections from full text to prevent prediction inside them."""
        lines = full_text.split("\n")
        result_lines = []
        inside_target_section = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not inside_target_section:
                    result_lines.append(line)
                continue
                
            low_clean = stripped.lower().rstrip(":")
            
            if inside_target_section:
                if low_clean in SECTION_HEADERS and low_clean not in names_to_remove:
                    inside_target_section = False
                    result_lines.append(line)
            else:
                if low_clean in names_to_remove:
                    inside_target_section = True
                else:
                    result_lines.append(line)
                    
        return "\n".join(result_lines)
