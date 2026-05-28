import mimetypes
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from Data_cleaning.clean_resumes import clean_text
from pipeline import (
    CertificationsExtractor,
    ExperienceExtractor,
    ProjectsExtractor,
    SkillsExtractor,
    extract_basic_infos,
    extract_education,
)


MODEL_NAME = "urchade/gliner_medium-v2.1"
ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_MIME_TYPES = {"application/pdf"}


class DependencyError(RuntimeError):
    """Raised when the parsing stack is not installed on the machine."""


def _ensure_pdf_dependencies() -> Any:
    try:
        from Text_extraction.dataset import extract_pdf_text
    except ImportError as exc:
        raise DependencyError(
            "Missing PDF extraction dependency. Install `pymupdf` first."
        ) from exc

    return extract_pdf_text


def _ensure_gliner() -> Any:
    try:
        # pyrefly: ignore [missing-import]
        from gliner import GLiNER
    except ImportError as exc:
        raise DependencyError(
            "Missing parser dependency. Install `gliner` and its model requirements first."
        ) from exc

    return GLiNER


@lru_cache(maxsize=1)
def _load_pipeline() -> Dict[str, Any]:
    gliner_cls = _ensure_gliner()
    model = gliner_cls.from_pretrained(MODEL_NAME)

    return {
        "model": model,
        "skills_extractor": SkillsExtractor(model),
        "experience_extractor": ExperienceExtractor(model),
        "certifications_extractor": CertificationsExtractor(),
        "projects_extractor": ProjectsExtractor(),
    }


def validate_uploaded_pdf(filename: str, content_type: str = "") -> None:
    suffix = Path(filename or "").suffix.lower()
    guessed_type = mimetypes.guess_type(filename or "")[0]

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF files are supported.")

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        if guessed_type not in ALLOWED_MIME_TYPES:
            raise ValueError("Uploaded file is not a valid PDF.")


def _parse_cleaned_resume(cleaned_text: str, filename: str, threshold: float) -> Dict[str, Any]:
    pipeline = _load_pipeline()
    model = pipeline["model"]

    basic_info = extract_basic_infos(cleaned_text, model, filename, threshold=threshold)
    skills = pipeline["skills_extractor"].extract(cleaned_text)
    education_data = extract_education(cleaned_text, model)
    raw_experience = pipeline["experience_extractor"].extract(
        cleaned_text,
        candidate_name=basic_info.get("full_name", ""),
    )
    experience = [
        {
            "company": job.get("company", ""),
            "role": job.get("role", ""),
            "start_date": job.get("start_date", ""),
            "end_date": job.get("end_date", ""),
        }
        for job in raw_experience
        if job.get("company") or job.get("role")
    ]

    certifications = pipeline["certifications_extractor"].extract(cleaned_text)
    projects = pipeline["projects_extractor"].extract(cleaned_text)

    return {
        "file_name": filename,
        **basic_info,
        "education": education_data.get("education", []),
        "experience": experience,
        "skills": skills,
        "certifications": certifications,
        "projects": projects,
    }


def parse_resume_bytes(
    file_bytes: bytes,
    filename: str,
    content_type: str = "",
    threshold: float = 0.4,
) -> Dict[str, Any]:
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    validate_uploaded_pdf(filename, content_type)
    extract_pdf_text = _ensure_pdf_dependencies()

    with tempfile.TemporaryDirectory(prefix="resume-upload-") as tmp_dir:
        upload_path = Path(tmp_dir) / Path(filename).name
        upload_path.write_bytes(file_bytes)
        raw_text = extract_pdf_text(upload_path)

    if not raw_text.strip():
        raise ValueError("No text could be extracted from the uploaded PDF.")

    cleaned_text = clean_text(raw_text)
    parsed_data = _parse_cleaned_resume(cleaned_text, filename, threshold)

    return {
        "file_name": filename,
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "parsed_data": parsed_data,
        "meta": {
            "raw_characters": len(raw_text),
            "cleaned_characters": len(cleaned_text),
            "skills_count": len(parsed_data.get("skills", [])),
            "education_count": len(parsed_data.get("education", [])),
            "experience_count": len(parsed_data.get("experience", [])),
            "certifications_count": len(parsed_data.get("certifications", [])),
            "projects_count": len(parsed_data.get("projects", [])),
        },
    }
