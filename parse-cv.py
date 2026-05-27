import json
import argparse
from pathlib import Path
# pyrefly: ignore [missing-import]
from gliner import GLiNER
from tqdm import tqdm

# Import the unified basic info extraction pipeline
from pipeline import extract_basic_infos, extract_name_from_filename, SkillsExtractor, extract_education, ExperienceExtractor


def get_original_filename(txt_stem: str, pdf_dir: Path) -> str:
    """Finds the original PDF/Image file in pdf_dir that matches the text file stem."""
    if not pdf_dir.exists():
        return f"{txt_stem}.pdf"
        
    # Search for any file matching the stem (case-insensitive)
    for p in pdf_dir.iterdir():
        if p.stem.lower() == txt_stem.lower():
            return p.name
            
    # Fallback to appending .pdf
    return f"{txt_stem}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract candidate names from resume text using GLiNER")
    parser.add_argument("--input-dir", default="Assets/resume_clean_dataset", help="Folder containing cleaned resume text files")
    parser.add_argument("--pdf-dir", default="Resume New 1", help="Folder containing original PDF/Image resumes")
    parser.add_argument("--output", default="output.json", help="Path to save the JSON output file")
    parser.add_argument("--threshold", type=float, default=0.4, help="Confidence threshold for GLiNER predictions")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    pdf_dir = Path(args.pdf_dir)
    output_path = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Find all txt files and sort them (using numeric sorting where possible)
    txt_files = sorted(input_dir.glob("*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
    if not txt_files:
        print(f"No .txt files found in {input_dir}")
        return

    print("Loading GLiNER model 'urchade/gliner_medium-v2.1'...")
    model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
    print("Model loaded successfully.")

    skills_extractor = SkillsExtractor(model)
    experience_extractor = ExperienceExtractor(model)

    results = []
    gliner_count = 0
    fallback_count = 0

    print(f"Processing {len(txt_files)} text files...")
    for idx, txt_path in enumerate(tqdm(txt_files), start=1):
        # 1. Map to original filename
        original_name = get_original_filename(txt_path.stem, pdf_dir)
        
        # 2. Read resume text
        text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        
        # 3. Extract basic info using the pipeline
        basic_info = extract_basic_infos(text, model, original_name, threshold=args.threshold)
        
        # 4. Extract skills
        skills = skills_extractor.extract(text)
        
        # 5. Extract education, certifications, and projects
        edu_data = extract_education(text, model)
        
        # 6. Extract experience
        raw_experience = experience_extractor.extract(text, candidate_name=basic_info.get("full_name", ""))
        experience = [
            {
                "company": job.get("company", ""),
                "role": job.get("role", ""),
                "start_date": job.get("start_date", ""),
                "end_date": job.get("end_date", ""),
            }
            for job in raw_experience
        ]
        
        # Track stats
        fallback_name = extract_name_from_filename(original_name)
        if basic_info["full_name"] == fallback_name:
            fallback_count += 1
        else:
            gliner_count += 1

        results.append({
            "id": idx,
            "file_name": original_name,
            **basic_info,
            "education": edu_data.get("education", []),
            "experience": experience,
            "skills": skills
        })

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"\nProcessing complete!")
    print(f"Total processed files: {len(results)}")
    print(f"Extracted by GLiNER: {gliner_count} ({gliner_count / len(results) * 100:.1f}%)")
    print(f"Extracted by fallback: {fallback_count} ({fallback_count / len(results) * 100:.1f}%)")
    print(f"Output saved to {output_path}")


if __name__ == "__main__":
    main()
