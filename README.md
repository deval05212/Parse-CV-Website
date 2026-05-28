# AI-Powered Resume PDF Parser Web Application

An elegant, high-performance web application and machine learning pipeline that extracts structured JSON data from PDF resumes. It leverages **GLiNER** (Generalist Model for Information Extraction) alongside **PyMuPDF** and **Tesseract OCR** (for scanned resumes) to clean, process, and structure resume content with exceptional precision.

---

## 🌟 Features

*   **Premium Web GUI (`home.html`)**: A beautiful, modern dark-themed user interface featuring:
    *   Interactive drag-and-drop file upload zone.
    *   Real-time side-by-side PDF previewing.
    *   Dynamic metrics display (character counts, skill count, detected jobs/projects/certs).
    *   Structured, tabular views of parsed education, experience, projects, and certifications.
    *   Collapsible raw and cleaned text panels.
*   **Dual-Engine Text Extraction (`Text_extraction`)**:
    *   **Native Text Extraction**: Fast and clean extraction from searchable PDFs using PyMuPDF.
    *   **OCR Fallback**: Automatically invokes Tesseract OCR and Pillow to extract text from scanned PDFs, image pages, or JPEG/PNG files.
*   **Advanced Preprocessing & Cleaning (`Data_cleaning`)**: 
    *   Normalizes and structures complex date expressions (e.g., standardizing ranges like `Jan 2020 - Present`).
    *   Cleans OCR letter-spacing errors (e.g., joining spaced-out characters like `S I N G H`).
    *   Standardizes phone numbers (handles Indian country codes and format variations).
    *   Normalizes section headers (mapping arbitrary headers to standardized sections like `EXPERIENCE`, `EDUCATION`, `SKILLS`).
    *   Repairs broken URLs, email prefixes, and strips layout boilerplate noise.
*   **Entity Extraction Pipeline (`pipeline`)**: Uses the `urchade/gliner_medium-v2.1` model to extract:
    *   **Basic Info**: Candidate Name, Job Role, Location, Email, Phone, LinkedIn, and GitHub.
    *   **Education**: Schools, degrees, and start/end dates.
    *   **Experience**: Company names, roles, and duration/date ranges.
    *   **Skills**: Tech stacks, programming languages, and frameworks.
    *   **Projects**: Academic/personal projects and descriptions.
    *   **Certifications**: Courses and professional certifications.
*   **Local Data Auditing**: Saves raw text, cleaned text, and final parsed JSON outputs locally to `stored_data/` for auditability and model tuning.

---

## 📂 Project Architecture

```
├── main.py                     # Entry point containing the HTTP server (BaseHTTPRequestHandler)
├── server.py                   # Simple script to run the backend service
├── resume_parser_service.py    # Service orchestrator loading the GLiNER model and extractors
├── home.html                   # Premium web frontend styling and interactive JS dashboard
├── requirements.txt            # Python dependencies
├── Data_cleaning/
│   └── clean_resumes.py        # Comprehensive regex-based text cleaning and standardization
├── Text_extraction/
│   └── dataset.py              # PyMuPDF-based text extractor with Tesseract OCR fallback
├── pipeline/                   # Extractor sub-modules utilizing GLiNER predictions
│   ├── __init__.py
│   ├── basic_info_extractor.py
│   ├── skills_extractor.py
│   ├── education_extractor.py
│   ├── experience_extractor.py
│   ├── certifications_extractor.py
│   └── projects_extractor.py
└── stored_data/                # Auto-created directory storing raw/cleaned/parsed text & JSON
    ├── raw_text/
    ├── cleaned_text/
    └── parsed_json/
```

---

## 🛠️ Setup & Installation

### 1. System Dependencies (Optional)
If you wish to parse **scanned PDFs** or **images** (JPEGs/PNGs) using the OCR fallback engine, you must install Tesseract OCR on your system:

*   **macOS (via Homebrew)**:
    ```bash
    brew install tesseract
    ```
*   **Linux (Ubuntu/Debian)**:
    ```bash
    sudo apt-get install tesseract-ocr
    ```
*   **Windows**:
    Download the installer from [UB Mannheim's Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki) and add the binary path to your system environment variables.

### 2. Python Environment Setup
We recommend setting up a virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Activate virtual environment (Windows)
# venv\Scripts\activate
```

### 3. Install Dependencies
Install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### Running the Web Server
Start the application using `server.py` or directly through `main.py`:

```bash
python server.py
```

By default, the server binds to:
*   **Host**: `192.168.0.251` (configurable via arguments)
*   **Port**: `5200`

#### Custom Host and Port Configuration
If you want to run the server on `localhost` or a different port:

```bash
python main.py --host 127.0.0.1 --port 8080
```

### Navigating the UI
1. Open your web browser and navigate to: `http://<your-host>:<your-port>/` (e.g., `http://192.168.0.251:5200` or `http://localhost:5200`).
2. Drop a resume PDF into the upload area or click to select a file.
3. The PDF will load in the preview panel, and the backend service will start parsing the file.
4. Once completed, the parsed JSON data will display in organized tabs, metrics will populate on the side, and the files are saved locally to `stored_data/`.

---

## 🔌 API Endpoints

### 1. Healthcheck
*   **Endpoint**: `GET /health`
*   **Response**:
    ```json
    { "status": "ok" }
    ```

### 2. Parse PDF
*   **Endpoint**: `POST /api/parse-pdf`
*   **Content-Type**: `multipart/form-data`
*   **Payload**: A form field named `pdf` containing the binary PDF file.
*   **Response**:
    ```json
    {
      "status": "success",
      "file_name": "John_Doe_Resume.pdf",
      "raw_text": "...",
      "cleaned_text": "...",
      "parsed_data": {
        "full_name": "John Doe",
        "job_role": "Software Engineer",
        "location": "Surat, Gujarat",
        "email": "johndoe@example.com",
        "phone": "+919999999999",
        "linkedin": "https://www.linkedin.com/in/johndoe",
        "github": "https://github.com/johndoe",
        "education": [...],
        "experience": [...],
        "skills": [...],
        "certifications": [...],
        "projects": [...]
      },
      "meta": {
        "raw_characters": 1250,
        "cleaned_characters": 1100,
        "skills_count": 12,
        "education_count": 1,
        "experience_count": 2,
        "certifications_count": 3,
        "projects_count": 2
      }
    }
    ```
