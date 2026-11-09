"""AI Resume ATS Score Checker - Streamlit + Google Gemini Flash."""

import json
import os
import re
from io import BytesIO

import streamlit as st
from docx import Document
from google import genai
from google.genai import types
from pypdf import PdfReader

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_RESUME_CHARS = 20000
MAX_JD_CHARS = 8000

PROMPT_TEMPLATE = """You are an expert ATS (Applicant Tracking System) analyst and professional resume reviewer.

Analyze the resume below{jd_clause}. Be honest, specific and strict. Do not invent facts that are not in the resume.

Scoring rubric (each 0-100):
- keywords: relevant skills/keywords{jd_keywords_note}
- formatting: ATS-friendly structure, standard section headings, readability, no tables/graphics problems
- content: quality of experience bullets, action verbs, measurable achievements
- completeness: contact info, summary, experience, education, skills sections present
Overall ats_score is a weighted result of these (keywords 35%, formatting 20%, content 30%, completeness 15%).

Return ONLY valid JSON with exactly this structure:
{{
  "ats_score": <integer 0-100>,
  "breakdown": {{"keywords": <int>, "formatting": <int>, "content": <int>, "completeness": <int>}},
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<string>", "..."],
  "missing_keywords": ["<string>", "..."],
  "improvements": [
    {{"priority": "High|Medium|Low", "issue": "<what is wrong>", "suggestion": "<exactly how to fix it>"}}
  ],
  "rewrite_examples": [
    {{"original": "<weak line from the resume>", "improved": "<stronger version, no fabricated numbers>"}}
  ]
}}

{jd_block}RESUME:
\"\"\"
{resume}
\"\"\"
"""


def extract_text(uploaded_file) -> str:
    """Extract plain text from an uploaded PDF, DOCX or TXT file."""
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("This PDF is password protected.")
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(pages).strip()

    if name.endswith(".docx"):
        doc = Document(BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text.strip())
        return "\n".join(parts).strip()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore").strip()

    raise ValueError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")


def parse_json_response(text: str) -> dict:
    """Parse JSON from the model, tolerating markdown fences or extra text."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _to_int(value, default=0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def normalize_result(raw: dict) -> dict:
    """Make sure every field exists and has the right type."""
    breakdown = raw.get("breakdown") or {}
    improvements = []
    for item in raw.get("improvements") or []:
        if isinstance(item, dict):
            improvements.append(
                {
                    "priority": str(item.get("priority", "Medium")).title(),
                    "issue": str(item.get("issue", "")),
                    "suggestion": str(item.get("suggestion", "")),
                }
            )
        elif isinstance(item, str):
            improvements.append({"priority": "Medium", "issue": item, "suggestion": ""})
    examples = [
        {"original": str(e.get("original", "")), "improved": str(e.get("improved", ""))}
        for e in (raw.get("rewrite_examples") or [])
        if isinstance(e, dict)
    ]
    return {
        "ats_score": _to_int(raw.get("ats_score")),
        "breakdown": {
            k: _to_int(breakdown.get(k))
            for k in ("keywords", "formatting", "content", "completeness")
        },
        "summary": str(raw.get("summary", "")),
        "strengths": [str(s) for s in (raw.get("strengths") or [])],
        "missing_keywords": [str(k) for k in (raw.get("missing_keywords") or [])],
        "improvements": improvements,
        "rewrite_examples": examples,
    }


def build_prompt(resume_text: str, job_description: str) -> str:
    resume_text = resume_text[:MAX_RESUME_CHARS]
    if job_description.strip():
        jd_clause = " against the job description provided"
        jd_keywords_note = " and how well they match the job description"
        jd_block = f'JOB DESCRIPTION:\n"""\n{job_description.strip()[:MAX_JD_CHARS]}\n"""\n\n'
    else:
        jd_clause = " for general ATS-friendliness (no specific job description given)"
        jd_keywords_note = " that are common for the candidate's apparent field"
        jd_block = ""
    return PROMPT_TEMPLATE.format(
        jd_clause=jd_clause,
        jd_keywords_note=jd_keywords_note,
        jd_block=jd_block,
        resume=resume_text,
    )


def analyze_resume(api_key: str, resume_text: str, job_description: str = "") -> dict:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_prompt(resume_text, job_description),
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return normalize_result(parse_json_response(response.text))


def get_api_key() -> str:
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:  # no secrets file locally
        key = ""
    return key or os.getenv("GEMINI_API_KEY", "")


def score_color(score: int) -> str:
    if score >= 75:
        return "green"
    if score >= 50:
        return "orange"
    return "red"


def render_results(result: dict) -> None:
    score = result["ats_score"]
    st.divider()
    st.subheader("Your ATS Score")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Overall ATS Score", f"{score}/100")
        st.progress(score / 100)
    with col2:
        st.markdown(f":{score_color(score)}[**{result['summary']}**]")

    st.subheader("Score Breakdown")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, result["breakdown"].items()):
        col.metric(label.title(), f"{value}/100")

    left, right = st.columns(2)
    with left:
        st.subheader("Strengths")
        for s in result["strengths"] or ["No strengths returned."]:
            st.markdown(f"- {s}")
    with right:
        st.subheader("Missing Keywords")
        if result["missing_keywords"]:
            st.markdown(", ".join(f"`{k}`" for k in result["missing_keywords"]))
        else:
            st.markdown("No major keywords missing.")

    st.subheader("Suggested Improvements")
    icons = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
    order = {"High": 0, "Medium": 1, "Low": 2}
    for item in sorted(result["improvements"], key=lambda i: order.get(i["priority"], 1)):
        with st.expander(f"{icons.get(item['priority'], '🟠')} {item['priority']}: {item['issue']}"):
            st.write(item["suggestion"] or "No details provided.")

    if result["rewrite_examples"]:
        st.subheader("Example Rewrites")
        for ex in result["rewrite_examples"]:
            st.markdown(f"**Before:** {ex['original']}")
            st.markdown(f"**After:** {ex['improved']}")
            st.write("")

    st.download_button(
        "Download report (JSON)",
        data=json.dumps(result, indent=2),
        file_name="ats_report.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="AI Resume ATS Checker", page_icon="📄", layout="wide")
    st.title("📄 AI Resume ATS Checker")
    st.caption("Upload your resume to get an ATS score and tips to improve it.")

    api_key = get_api_key()
    with st.sidebar:
        st.header("Settings")
        if not api_key:
            api_key = st.text_input("Gemini API key", type="password",
                                    help="Get a free key at aistudio.google.com")
        else:
            st.success("API key loaded")
        st.markdown("Your resume is sent to Google's Gemini API for analysis. "
                    "Avoid uploading data you don't want shared.")

    uploaded = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
    job_description = st.text_area(
        "Job description (optional, for a more accurate score)",
        height=150,
        placeholder="Paste the job description here to match keywords...",
    )

    if st.button("Analyze Resume", type="primary", disabled=uploaded is None):
        if not api_key:
            st.error("Please provide a Gemini API key in the sidebar.")
            return
        try:
            with st.spinner("Reading your resume..."):
                text = extract_text(uploaded)
        except Exception as exc:
            st.error(f"Could not read the file: {exc}")
            return

        if len(text) < 100:
            st.error("Very little text was found. If your resume is a scanned image, "
                     "upload a text-based PDF or DOCX instead (ATS systems can't read images either).")
            return

        try:
            with st.spinner("Analyzing with Gemini..."):
                result = analyze_resume(api_key, text, job_description)
        except json.JSONDecodeError:
            st.error("The AI returned an unreadable response. Please try again.")
            return
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            return

        st.session_state["result"] = result

    if "result" in st.session_state:
        render_results(st.session_state["result"])


if __name__ == "__main__":
    main()
