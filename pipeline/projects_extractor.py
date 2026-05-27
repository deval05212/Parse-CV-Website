import re
try:
    from pipeline.skills_extractor import TECH_KEYWORDS, NORM_MAP
except ImportError:
    TECH_KEYWORDS = set()
    NORM_MAP = {}

class ProjectsExtractor:
    """
    Modular project extractor based on section parsing and layout heuristics.
    Separates technology stacks and developer roles from project titles,
    and returns a structured list of project dictionaries.
    """
    
    PROJECT_HEADERS = [
        "projects", "project", "personal projects", "academic projects", "college projects",
        "key projects", "mini projects", "major projects", "recent projects", "project work",
        "projects worked on", "academic projects", "portfolio"
    ]

    NEXT_HEADERS = [
        "education", "experience", "work experience", "professional experience",
        "skills", "technical skills", "summary", "profile", "objective", "interests",
        "languages", "hobbies", "declaration", "achievements", "awards", 
        "positions of responsibility", "extra curricular", "extracurricular",
        "certifications", "certification", "certificates", "certificate", "courses",
        "projects", "project", "additional details", "additional info", "additional information",
        "personal details", "personal information", "references", "key skills"
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

    JUNK_PROJECT_TITLES = {"live", "github", "link", "links", "demo", "code", "website", "project", "projects", "url", "video"}

    ADDITIONAL_TECH = {
        # Backend / DB / API
        "jdbc", "springboot", "django", "mern", "mean", "lamp", "html/css", "css/html", "stack", "api", "apis", 
        "restful", "rest", "mangopay", "shuftipro", "socket.io", "encryption", "jwt", "bcrypt", "gcp", "s3", 
        "rabbitmq", "jsp", "tavily", "langgraph", "langchain", "shap", "streamlit", "axios", "stripe", "paypal",
        "plaid", "ach", "sendgrid", "swagger", "docs", "dall", "e3", "openai", "knex", "sequelize", "mongoose",
        "hibernate", "spring", "postgressql", "postgre", "knex.js", "express.js", "node.js", "react.js",
        "spring-boot", "aws-sdk", "vector", "embedding-3-small", "gpt-4o-mini", "dall-e3", "pinecone",
        "weaviate", "faiss", "prompt", "nlp", "llm", "llms", "rag", "pytorch", "tensorflow", "keras",
        "scikit-learn", "xgboost", "mlflow", "dvc", "yolo", "opencv", "dalle3", "dall-e-3",
        "boot", "swing", "dot", "core", "postgresql",
        # Frontend / styling
        "bootstrap", "tailwind", "sass", "less", "css", "html", "javascript", "typescript", "angular", "react", "redux", "thunk"
    }

    STRIP_WORDS = {
        "with", "using", "in", "via", "based", "on", "and", "or", "for", "developed", "built", "made",
        "-", "|", "/", ",", "&", "(", ")", "[", "]", ":"
    }

    ROLE_WORDS = {
        "developer", "development", "engineer", "engineering", "intern", "trainee", 
        "full", "stack", "frontend", "front-end", "backend", "back-end", "software", "web",
        "lead", "senior", "junior", "role", "analyst"
    }

    ROLE_PATTERNS = [
        r'\bfull\s*stack\s*developer\b',
        r'\bfull\s*stack\s*engineer\b',
        r'\bfrontend\s*developer\b',
        r'\bfront-end\s*developer\b',
        r'\bfrontend\s*engineer\b',
        r'\bfront-end\s*engineer\b',
        r'\bbackend\s*developer\b',
        r'\bback-end\s*developer\b',
        r'\bbackend\s*engineer\b',
        r'\bback-end\s*engineer\b',
        r'\bsoftware\s*developer\b',
        r'\bsoftware\s*engineer\b',
        r'\bweb\s*developer\b',
        r'\bdeveloper\b',
        r'\bengineer\b'
    ]

    DATE_RE = re.compile(
        r'\b(?:(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}|(?:19|20)\d{2}|'
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:19|20)\d{2})\b',
        re.I
    )

    KEY_VALUE_RE = re.compile(
        r'^(?i)\s*(?:type|backend|frontend|database|tech\s*stack|technologies|tools|libraries|environment|key\s*concept|concept|link|github|role|duration|date)\s*:'
    )

    def __init__(self, model=None):
        self.model = model
        self.ALL_TECH_KEYWORDS = TECH_KEYWORDS.union(self.ADDITIONAL_TECH)

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

    def normalize_tech(self, name: str) -> str:
        cleaned = name.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★&").lower()
        if not cleaned:
            return ""
        
        local_norm_map = {
            "springboot": "Spring Boot",
            "spring boot": "Spring Boot",
            "spring-boot": "Spring Boot",
            "spring": "Spring",
            "express.js": "Express.js",
            "expressjs": "Express.js",
            "express": "Express.js",
            "socket.io": "Socket.io",
            "jwt": "JWT",
            "bcrypt": "Bcrypt",
            "s3": "AWS S3",
            "aws s3": "AWS S3",
            "gcp": "GCP",
            "api": "API",
            "apis": "APIs",
            "restful": "RESTful API",
            "rest": "REST API",
            "rest api": "REST API",
            "rest apis": "REST API",
            "sendgrid": "SendGrid",
            "swagger": "Swagger",
            "rabbitmq": "RabbitMQ",
            "knex": "Knex",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mysql": "MySQL",
            "mongodb": "MongoDB",
            "stripe": "Stripe",
            "paypal": "PayPal",
            "plaid": "Plaid",
            "ach": "ACH",
            "openai": "OpenAI",
            "dall": "DALL-E",
            "e3": "E3",
            "dall e3": "DALL-E 3",
            "dall-e3": "DALL-E 3",
            "dalle3": "DALL-E 3",
            "shuftipro": "ShuftiPro",
            "mangopay": "MangoPay",
            "langchain": "LangChain",
            "langgraph": "LangGraph",
            "tavily": "Tavily",
            "streamlit": "Streamlit",
            "shap": "SHAP",
            "redux": "Redux",
            "thunk": "Redux Thunk",
            "firebase": "Firebase",
            "jwt": "JWT",
            "jdbc": "JDBC",
            "jsp": "JSP"
        }
        
        combined_map = {**NORM_MAP, **local_norm_map}
        if cleaned in combined_map:
            return combined_map[cleaned]
        if cleaned.islower():
            if cleaned in {"api", "apis", "jwt", "gcp", "s3", "aws", "xml", "json", "rest", "db", "sql", "mvc", "cdn", "kyc", "aml", "crud", "css", "html", "b2b", "crm"}:
                return cleaned.upper()
            return cleaned.title()
        return name

    def split_by_role(self, title: str) -> tuple[str, str]:
        best_match = None
        for pattern in self.ROLE_PATTERNS:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                if best_match is None or match.start() < best_match.start():
                    best_match = match
                    
        if best_match:
            split_pos = best_match.start()
            prefix = title[:split_pos].strip()
            suffix = title[split_pos:].strip()
            if prefix:
                return prefix, suffix
                
        return title, ""

    def extract_techs_from_text(self, text: str) -> list[str]:
        extracted = []
        text_lower = text.lower()
        for tech in self.ALL_TECH_KEYWORDS:
            if len(tech) > 2:
                pattern = rf"\b{re.escape(tech)}\b"
                if re.search(pattern, text_lower):
                    extracted.append(tech)
            elif tech in {"c", "go"}:
                pattern = rf"\b{re.escape(tech)}\b"
                if re.search(pattern, text_lower):
                    extracted.append(tech)
        return [self.normalize_tech(t) for t in extracted]

    def clean_project_title(self, title: str) -> tuple[str, list[str]]:
        prefix, suffix = self.split_by_role(title)
        if suffix:
            techs = self.extract_techs_from_text(suffix)
            cleaned_prefix = self.balance_parens(self.strip_punctuation(prefix))
            return cleaned_prefix, techs
            
        matches = list(re.finditer(r'\b[\w\+\-\.#]+|[,\-\|\(\)\[\]/&:]', title))
        tokens = [m.group(0) for m in matches]
        
        split_idx = len(tokens)
        extracted_techs = []
        
        for i in range(len(tokens) - 1, -1, -1):
            token = tokens[i]
            token_lower = token.lower()
            
            is_tech = (token_lower in TECH_KEYWORDS) or (token_lower in self.ADDITIONAL_TECH)
            is_strip = (token_lower in self.STRIP_WORDS) or (token in self.STRIP_WORDS)
            is_role = (token_lower in self.ROLE_WORDS)
            is_version = re.match(r'^v?\d+(\.\d+)?$', token_lower) is not None
            
            if is_tech:
                extracted_techs.append(token)
                split_idx = i
            elif is_strip or is_role or is_version:
                split_idx = i
            else:
                break
                
        if split_idx < len(tokens):
            cut_pos = matches[split_idx].start()
            cleaned_title = title[:cut_pos]
            cleaned_title = self.balance_parens(self.strip_punctuation(cleaned_title))
            if cleaned_title:
                return cleaned_title, [self.normalize_tech(t) for t in reversed(extracted_techs)]
                
        return self.balance_parens(self.strip_punctuation(title)), []

    def _isolate_section(self, text: str) -> str:
        lines = text.split("\n")
        start_idx = -1
        for i, line in enumerate(lines):
            clean_line = re.sub(r'^[\s•\-\*⚫■★]+', '', line.strip().lower())
            clean_line = re.sub(r'[:\-.]+$', '', clean_line).strip()
            clean_line = re.sub(r'\s+', ' ', clean_line)
            if clean_line in self.PROJECT_HEADERS:
                start_idx = i + 1
                break
                
        if start_idx == -1:
            for i, line in enumerate(lines):
                clean_line = line.strip().lower()
                if any(h == clean_line for h in self.PROJECT_HEADERS):
                    start_idx = i + 1
                    break
                if any(f" {h} " in f" {clean_line} " for h in self.PROJECT_HEADERS) and len(clean_line) < 40:
                    if not clean_line.endswith("."):
                        start_idx = i + 1
                        break
                    
        if start_idx == -1:
            return ""
            
        end_idx = len(lines)
        for i in range(start_idx, len(lines)):
            clean_line = re.sub(r'^[\s•\-\*⚫■★]+', '', lines[i].strip().lower())
            clean_line = re.sub(r'[:\-.]+$', '', clean_line).strip()
            if clean_line in self.NEXT_HEADERS and clean_line not in self.PROJECT_HEADERS:
                end_idx = i
                break
            if re.match(r'^(?i)\s*(?:email|mobile|phone|contact|linkedin|github)\s*:', clean_line):
                end_idx = i
                break
                
        return "\n".join(lines[start_idx:end_idx]).strip()

    def extract(self, text: str) -> list[dict]:
        section_text = self._isolate_section(text)
        if not section_text:
            return []
            
        lines = [l.strip() for l in section_text.split("\n") if l.strip()]
        projects = []
        
        current_proj = None
        
        for line in lines:
            line_clean = re.sub(r'^[\s•\-\*⚫■★+·]+', '', line).strip()
            if not line_clean:
                continue
                
            is_bullet = line.strip().startswith(("-", "*", "•", "⚫", "■", "★", "+", "·"))
            ends_with_period = line_clean.endswith((".", ";", "!"))
            
            first_word = line_clean.split()[0].lower().strip(".,;:()") if line_clean.split() else ""
            is_action_verb = first_word in self.ACTION_VERBS
            
            is_link = line_clean.lower().startswith(("link:", "github:", "http://", "https://", "live:"))
            is_tech_stack_indicator = line_clean.lower().startswith(("tech stack:", "technologies:", "tools used:", "environment:", "libraries:"))
            
            is_key_value = bool(self.KEY_VALUE_RE.match(line_clean))
            is_date = bool(self.DATE_RE.match(line_clean)) and len(line_clean) < 20
            
            words = [w.lower().strip(" \t\n\r.,;:-|/()[]{}*•⚫■★&") for w in line_clean.split()]
            tech_words_count = sum(1 for w in words if w in TECH_KEYWORDS or w in self.ADDITIONAL_TECH)
            is_mostly_tech = len(words) > 0 and (tech_words_count / len(words)) >= 0.6
            
            # Clean title first to check length
            cleaned_title_temp, _ = self.clean_project_title(line_clean)
            starts_with_cap = len(cleaned_title_temp) > 0 and (cleaned_title_temp[0].isupper() or cleaned_title_temp[0].isdigit())
            
            prev_line_continued = False
            if current_proj and current_proj["description"]:
                last_desc = current_proj["description"].strip()
                if last_desc:
                    last_word = last_desc.split()[-1].lower().strip(".:;!?()[]{}")
                    if last_desc.endswith(",") or last_word in {"and", "or", "with", "using", "for", "to", "in", "on", "at", "by", "of", "the", "a", "an", "is", "are", "from", "implemented"}:
                        prev_line_continued = True

            is_title = (
                not prev_line_continued and
                not is_bullet and 
                not ends_with_period and 
                not is_action_verb and 
                not is_link and 
                not is_tech_stack_indicator and 
                not is_key_value and 
                not is_date and 
                not is_mostly_tech and 
                starts_with_cap and 
                len(cleaned_title_temp) < 80 and 
                cleaned_title_temp.lower().strip(" \t\n\r.,;:-|/()[]{}*•⚫■★") not in self.JUNK_PROJECT_TITLES
            )
            
            if is_title:
                if current_proj:
                    projects.append(current_proj)
                current_proj = {
                    "project_name": line_clean,
                    "technologies": [],
                    "description": ""
                }
            else:
                if current_proj:
                    if is_tech_stack_indicator or is_mostly_tech:
                        content = line_clean
                        for indicator in ["tech stack:", "technologies:", "tools used:", "environment:", "libraries:"]:
                            if content.lower().startswith(indicator):
                                content = content[len(indicator):].strip()
                                break
                        parts = re.split(r'[,;/]|\band\b', content, flags=re.IGNORECASE)
                        if len(parts) <= 1:
                            space_parts = content.split()
                            tech_count = sum(1 for p in space_parts if p.lower().strip(" \t\n\r.,;:-|/()[]{}*•⚫■★") in self.ALL_TECH_KEYWORDS)
                            if tech_count >= 2:
                                parts = space_parts
                        
                        for part in parts:
                            part_clean = part.strip(" \t\n\r.,;:-|/()[]{}*•⚫■★")
                            if part_clean:
                                part_lower = part_clean.lower()
                                if (part_lower in TECH_KEYWORDS) or (part_lower in self.ADDITIONAL_TECH):
                                    current_proj["technologies"].append(self.normalize_tech(part_clean))
                    elif is_key_value:
                        if current_proj["description"]:
                            current_proj["description"] += " " + line_clean
                        else:
                            current_proj["description"] = line_clean
                    elif is_date:
                        continue
                    else:
                        if current_proj["description"]:
                            current_proj["description"] += " " + line_clean
                        else:
                            current_proj["description"] = line_clean
                else:
                    current_proj = {
                        "project_name": "Project",
                        "technologies": [],
                        "description": line_clean
                    }
                    
        if current_proj:
            projects.append(current_proj)
            
        valid_projects = []
        for p in projects:
            name = self.strip_punctuation(p["project_name"])
            if name and name.lower() not in {"project", "projects"} and len(name) > 3:
                cleaned_title, trailing_techs = self.clean_project_title(name)
                if not cleaned_title:
                    continue
                
                cleaned_title = self.balance_parens(self.strip_punctuation(cleaned_title))
                if not cleaned_title or cleaned_title.lower() in {"project", "projects"}:
                    continue
                
                all_techs = p["technologies"] + trailing_techs
                
                combined_text = (name + " " + p["description"]).lower()
                for tech in self.ALL_TECH_KEYWORDS:
                    if len(tech) > 2:
                        pattern = rf"\b{re.escape(tech)}\b"
                        if re.search(pattern, combined_text):
                            all_techs.append(self.normalize_tech(tech))
                    elif tech in {"c", "go"}:
                        pattern = rf"\b{re.escape(tech)}\b"
                        if re.search(pattern, combined_text):
                            all_techs.append(self.normalize_tech(tech))
                
                seen_techs = set()
                dedup_techs = []
                for t in all_techs:
                    t_norm = t.lower()
                    if t_norm and t_norm not in seen_techs and t_norm not in {"developer", "development", "engineer", "engineering", "concept", "concepts", "stack", "system", "dot", "core", "boot"}:
                        seen_techs.add(t_norm)
                        dedup_techs.append(t)
                
                cleaned_desc = re.sub(r'\s+', ' ', p["description"]).strip()
                if not cleaned_desc and not dedup_techs:
                    continue
                    
                valid_projects.append({
                    "project_name": cleaned_title,
                    "technologies": dedup_techs,
                    "description": cleaned_desc
                })
                
        return valid_projects
