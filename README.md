# 📄 AI Resume ATS Checker

Upload your resume (PDF, DOCX or TXT) and get an **ATS score**, a score breakdown, missing keywords, prioritized improvements and example rewrites. Optionally paste a job description for a more accurate, role-specific score.

Built with **Streamlit** and **Google Gemini Flash**.

## Features
- Reads PDF, DOCX and TXT resumes
- Overall ATS score (0-100) plus Keywords / Formatting / Content / Completeness breakdown
- Strengths, missing keywords, and High/Medium/Low priority fixes
- Before/after rewrite examples
- Optional job-description matching
- Download the report as JSON

## Run locally
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey), then either:

- set it as an environment variable:
  - Mac/Linux: `export GEMINI_API_KEY="your_key"`
  - Windows (PowerShell): `$env:GEMINI_API_KEY="your_key"`
- or create `.streamlit/secrets.toml`:
  ```toml
  GEMINI_API_KEY = "your_key"
  ```
- or just paste it into the app's sidebar.

Run:
```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this repo to GitHub (do **not** commit your API key or `secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app**, choose your repo, branch `main`, and main file `app.py`.
4. Open **Advanced settings → Secrets** and add:
   ```toml
   GEMINI_API_KEY = "your_key"
   ```
5. Click **Deploy**.

## Configuration
The model defaults to `gemini-2.5-flash`. To use a different Gemini Flash model, set the `GEMINI_MODEL` environment variable (or secret).

## Notes
- Scanned/image-only resumes can't be read; use a text-based PDF or DOCX.
- The score is an AI estimate, not the output of a real ATS.
- Resume text is sent to the Gemini API for analysis.

## Project structure
```
app.py
requirements.txt
README.md
```
