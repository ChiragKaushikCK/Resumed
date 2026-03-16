import streamlit as st
import os
import json
import io
import time
import pandas as pd
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from xhtml2pdf import pisa

try:
    api_key = st.secrets["OPENROUTER_API_KEY"]
except:
    api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    st.error("API key missing")
    st.stop()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

st.set_page_config(page_title="Resumed | Live AI Resume Builder", layout="wide", page_icon="📄")

st.title("📄 Resumed - Build your resume with AI")

st.info("Watch your resume being created word-by-word in real time.")


def render_template(data):

    html = f"""
<html>
<head>
<style>
body {{font-family: Arial;padding:40px;}}
h1 {{text-align:center;margin-bottom:5px;}}
.contact {{text-align:center;margin-bottom:20px;}}
.section-title {{border-bottom:1px solid black;margin-top:20px;font-weight:bold;}}
</style>
</head>
<body>
<h1>{data.get("name","")}</h1>
<div class="contact">{data.get("contact","")}</div>
"""

    if data.get("summary"):
        html += f"""
<div class="section-title">Professional Summary</div>
<p>{data['summary']}</p>
"""

    if data.get("experience"):
        html += """<div class="section-title">Experience</div>"""
        for exp in data["experience"]:
            html += f"""
<p><b>{exp.get('title','')}</b> - {exp.get('company','')}<br>{exp.get('duration','')}</p>
<p>{exp.get('description','')}</p>
"""

    if data.get("projects"):
        html += """<div class="section-title">Projects</div>"""
        for proj in data["projects"]:
            html += f"""
<p><b>{proj.get('name','')}</b> ({proj.get('tech_stack','')})</p>
<p>{proj.get('description','')}</p>
"""

    if data.get("education"):
        html += """<div class="section-title">Education</div>"""
        for edu in data["education"]:
            html += f"""
<p><b>{edu.get('university','')}</b><br>{edu.get('degree','')} ({edu.get('year','')})</p>
"""

    if data.get("skills"):
        html += f"""
<div class="section-title">Skills</div>
<p>{data['skills']}</p>
"""

    html += "</body></html>"

    return html


def generate_resume_stream(raw_text, builder_box, preview_box):

    prompt = """
You are an expert resume writer.

Extract resume info and return STRICT JSON:

{
"name":"",
"contact":"",
"summary":"",
"experience":[{"title":"","company":"","duration":"","description":""}],
"projects":[{"name":"","tech_stack":"","description":""}],
"education":[{"degree":"","university":"","year":""}],
"skills":""
}
"""

    stream = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role":"system","content":prompt},
            {"role":"user","content":raw_text}
        ],
        stream=True
    )

    generated = ""

    for chunk in stream:

        if chunk.choices[0].delta.content:

            token = chunk.choices[0].delta.content
            generated += token

            builder_box.markdown(f"""
### 🤖 AI Writing Resume

```json
{generated}
```
""")

            try:
                data = json.loads(generated)
                html = render_template(data)

                preview_box.components.v1.html(
                    html,
                    height=700,
                    scrolling=True
                )
            except:
                pass

            time.sleep(0.01)

    return json.loads(generated)


def generate_docx(data):

    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    name = doc.add_heading(data.get("name",""),0)
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph(data.get("contact",""))
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if data.get("summary"):
        doc.add_heading("Summary",level=1)
        doc.add_paragraph(data["summary"])

    if data.get("experience"):
        doc.add_heading("Experience",level=1)
        for exp in data["experience"]:
            doc.add_paragraph(f"{exp['title']} - {exp['company']} ({exp['duration']})")
            doc.add_paragraph(exp["description"])

    if data.get("projects"):
        doc.add_heading("Projects",level=1)
        for proj in data["projects"]:
            doc.add_paragraph(f"{proj['name']} ({proj['tech_stack']})")
            doc.add_paragraph(proj["description"])

    if data.get("education"):
        doc.add_heading("Education",level=1)
        for edu in data["education"]:
            doc.add_paragraph(f"{edu['degree']} - {edu['university']} ({edu['year']})")

    if data.get("skills"):
        doc.add_heading("Skills",level=1)
        doc.add_paragraph(data["skills"])

    bio = io.BytesIO()
    doc.save(bio)

    return bio.getvalue()


def generate_pdf(html):

    result = io.BytesIO()

    pdf = pisa.pisaDocument(
        io.BytesIO(html.encode("UTF-8")),
        result
    )

    if not pdf.err:
        return result.getvalue()

    return None


if "resume_data" not in st.session_state:
    st.session_state.resume_data = None


tab1, tab2 = st.tabs(["📝 Input", "📄 Resume"])

with tab1:

    st.subheader("Paste your raw information")

    raw_text = st.text_area(
        "Your background",
        height=250,
        placeholder="My name is John Doe. Data scientist at XYZ. Built ML systems."
    )

    if st.button("✨ Generate Resume", use_container_width=True):

        if raw_text.strip():

            col1, col2 = st.columns(2)

            with col1:
                builder_box = st.empty()

            with col2:
                preview_box = st.empty()

            progress = st.progress(0)

            st.markdown("### 🧠 AI Thinking")

            st.write("🔍 Extracting details...")
            progress.progress(25)
            time.sleep(1)

            st.write("🧠 Writing professional summary...")
            progress.progress(50)
            time.sleep(1)

            st.write("📊 Expanding experience...")
            progress.progress(70)
            time.sleep(1)

            data = generate_resume_stream(raw_text, builder_box, preview_box)

            st.session_state.resume_data = data

            progress.progress(100)

            st.success("Resume generated!")

        else:
            st.warning("Please enter details.")


with tab2:

    if st.session_state.resume_data:

        data = st.session_state.resume_data

        html = render_template(data)

        st.components.v1.html(
            html,
            height=800,
            scrolling=True
        )

        col1, col2 = st.columns(2)

        with col1:

            docx = generate_docx(data)

            st.download_button(
                "Download DOCX",
                docx,
                file_name="resume.docx"
            )

        with col2:

            pdf = generate_pdf(html)

            if pdf:

                st.download_button(
                    "Download PDF",
                    pdf,
                    file_name="resume.pdf"
                )

    else:

        st.info("Generate resume first.")
