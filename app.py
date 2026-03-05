import streamlit as st
import os
import json
import io
from openai import OpenAI
from docx import Document
from xhtml2pdf import pisa

# ==========================================
# 1. API Configuration (OpenRouter)
# ==========================================
# Safely try to get the key from Streamlit secrets (for Cloud Deployment)
try:
    api_key = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
    # Fallback to local environment variable (for Local Testing)
    api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    st.error("⚠️ API key not found. Please set it in Streamlit Secrets or as an environment variable.")
    st.stop()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# ==========================================
# 2. HTML/CSS Resume Templates
# ==========================================
def render_faang_template(data):
    """A clean, highly professional, left-aligned template."""
    html = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 30px; color: #000;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px;">
            <h1 style="margin: 0; font-size: 28px;">{data.get('name', 'Your Name')}</h1>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #333;">{data.get('contact', 'Email | Phone | LinkedIn')}</p>
        </div>
        
        <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; text-transform: uppercase; font-size: 14px;">Summary</h3>
        <p style="font-size: 12px; line-height: 1.4; margin-top: 5px;">{data.get('summary', '')}</p>
        
        <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; text-transform: uppercase; font-size: 14px;">Experience</h3>
    """
    for exp in data.get('experience', []):
        html += f"""
        <div style="margin-top: 8px;">
            <div style="display: flex; justify-content: space-between;">
                <b style="font-size: 13px;">{exp.get('title', '')} at {exp.get('company', '')}</b>
                <span style="font-size: 12px; color: #555;">{exp.get('duration', '')}</span>
            </div>
            <p style="font-size: 12px; margin: 3px 0; line-height: 1.4;">{exp.get('description', '')}</p>
        </div>
        """
        
    # --- Projects Section ---
    if data.get('projects') and len(data['projects']) > 0:
        html += f"""
            <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; text-transform: uppercase; font-size: 14px;">Projects</h3>
        """
        for proj in data.get('projects', []):
            html += f"""
            <div style="margin-top: 8px;">
                <div style="display: flex; justify-content: space-between;">
                    <b style="font-size: 13px;">{proj.get('name', '')}</b>
                    <span style="font-size: 12px; color: #555;">{proj.get('tech_stack', '')}</span>
                </div>
                <p style="font-size: 12px; margin: 3px 0; line-height: 1.4;">{proj.get('description', '')}</p>
            </div>
            """
        
    html += f"""
        <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; text-transform: uppercase; font-size: 14px;">Education</h3>
    """
    for edu in data.get('education', []):
        html += f"""
        <div style="display: flex; justify-content: space-between; margin-top: 8px;">
            <div>
                <b style="font-size: 13px;">{edu.get('university', '')}</b>
                <p style="margin: 0; font-size: 12px;">{edu.get('degree', '')}</p>
            </div>
            <span style="font-size: 12px; color: #555;">{edu.get('year', '')}</span>
        </div>
        """

    html += f"""
        <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; text-transform: uppercase; font-size: 14px;">Skills</h3>
        <p style="font-size: 12px; line-height: 1.4; margin-top: 5px;">{data.get('skills', '')}</p>
    </div>
    """
    return html

def render_xyz_template(data):
    """A styled template with different fonts and colored accents."""
    html = render_faang_template(data).replace(
        "font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;", 
        "font-family: 'Georgia', serif;"
    ).replace(
        "border-bottom: 2px solid #000;", 
        "border-bottom: 2px solid #2a75d3;"
    ).replace(
        "text-transform: uppercase;",
        "color: #2a75d3; text-transform: uppercase;"
    )
    return html

# ==========================================
# 3. AI Processing (OpenRouter GPT-4o-mini)
# ==========================================
def extract_details_with_ai(raw_text):
    """Uses GPT-4o-mini to parse text, infer missing details, and structure as JSON."""
    
    prompt = """
    You are an expert resume writer and career coach. Extract the information from the user's raw text and format it STRICTLY as a JSON object. 
    
    CRITICAL INSTRUCTIONS:
    1. If the user provides incomplete details (e.g., just a job title but no description), you MUST auto-generate a professional, realistic description with bullet points based on standard industry practices for that role.
    2. If the user lacks a summary, write a compelling professional summary based on the provided experience.
    3. Infer relevant skills if they are missing but implied by the experience or projects.
    4. Ensure all descriptions are highly professional, grammatically perfect, and action-oriented.
    5. Do not include markdown formatting like ```json in the output, just return the raw JSON.
    
    Required JSON Schema:
    {
        "name": "Full Name",
        "contact": "Email | Phone | Location / Links",
        "summary": "A strong 2-3 sentence professional summary.",
        "experience": [
            {
                "title": "Job Title",
                "company": "Company Name",
                "duration": "Start Date - End Date",
                "description": "A detailed paragraph or bullet points summarizing key achievements."
            }
        ],
        "projects": [
            {
                "name": "Project Name",
                "tech_stack": "Technologies used",
                "description": "Detailed description of the project, problem solved, and impact."
            }
        ],
        "education": [
            {
                "degree": "Degree Name",
                "university": "University Name",
                "year": "Graduation Year"
            }
        ],
        "skills": "Comma-separated list of technical and soft skills"
    }
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Error communicating with OpenRouter API: {e}")
        return None

# ==========================================
# 4. File Export Generators (Word & PDF)
# ==========================================
def generate_docx(data):
    """Builds a formatted Word document from the JSON data."""
    doc = Document()
    
    # Header
    name = doc.add_heading(data.get('name', 'Your Name'), 0)
    name.alignment = 1 # Center
    contact = doc.add_paragraph(data.get('contact', ''))
    contact.alignment = 1
    
    # Summary
    doc.add_heading('Professional Summary', level=1)
    doc.add_paragraph(data.get('summary', ''))
    
    # Experience
    doc.add_heading('Experience', level=1)
    for exp in data.get('experience', []):
        p = doc.add_paragraph()
        p.add_run(exp.get('title', '')).bold = True
        p.add_run(f" at {exp.get('company', '')}")
        p.add_run(f" | {exp.get('duration', '')}").italic = True
        doc.add_paragraph(exp.get('description', ''))
        
    # Projects
    if data.get('projects'):
        doc.add_heading('Projects', level=1)
        for proj in data.get('projects', []):
            p = doc.add_paragraph()
            p.add_run(proj.get('name', '')).bold = True
            if proj.get('tech_stack'):
                p.add_run(f" | {proj.get('tech_stack', '')}").italic = True
            doc.add_paragraph(proj.get('description', ''))
            
    # Education
    doc.add_heading('Education', level=1)
    for edu in data.get('education', []):
        p = doc.add_paragraph()
        p.add_run(edu.get('university', '')).bold = True
        p.add_run(f" - {edu.get('degree', '')} ({edu.get('year', '')})")
        
    # Skills
    doc.add_heading('Skills', level=1)
    doc.add_paragraph(data.get('skills', ''))
    
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(html_content):
    """Converts the HTML string directly to a PDF file."""
    full_html = f"<html><body>{html_content}</body></html>"
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(full_html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

# ==========================================
# 5. Streamlit UI Elements
# ==========================================
st.set_page_config(page_title="AI Resume Builder", layout="wide")

st.title("📄 AI Resume Builder")
st.write("Build a perfectly formatted resume in seconds. Just type what you know, and the AI will professionally expand and format the rest.")

st.subheader("1. Choose a Template")
template_choice = st.selectbox("Select your preferred format:", ["FAANG Template", "XYZ Format"])

st.subheader("2. Enter Your Details")

st.info("""
**💡 Pro Tip: Don't worry about perfect formatting or writing full sentences.**
* Include your basic info, jobs, **projects**, and education.
* If you just type *"Built a React app for e-commerce"*, the AI will automatically write a professional, detailed description for it!
* The AI will also auto-generate a Professional Summary and infer your Skills if you leave them out.
""")

resume_data = None
raw_text = st.text_area("Dump your experience and projects here:", height=250)

if st.button("Generate & Enhance Resume"):
    if raw_text.strip():
        with st.spinner("Analyzing data and generating professional descriptions..."):
            resume_data = extract_details_with_ai(raw_text)
    else:
        st.warning("Please paste some text before generating.")

# ==========================================
# 6. Output Render & Downloads
# ==========================================
if resume_data:
    st.success("Resume generated successfully!")
    st.markdown("---")
    
    # Generate the HTML layout for preview
    if template_choice == "FAANG Template":
        final_html = render_faang_template(resume_data)
    else:
        final_html = render_xyz_template(resume_data)
        
    st.subheader("Preview")
    st.components.v1.html(final_html, height=800, scrolling=True)
    
    st.markdown("---")
    st.subheader("Export Your Resume")
    
    col1, col2 = st.columns(2)
    
    with col1:
        docx_file = generate_docx(resume_data)
        st.download_button(
            label="📄 Download as Word (.docx)",
            data=docx_file,
            file_name=f"{resume_data.get('name', 'Resume').replace(' ', '_')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    with col2:
        pdf_file = generate_pdf(final_html)
        if pdf_file:
            st.download_button(
                label="📥 Download as PDF (.pdf)",
                data=pdf_file,
                file_name=f"{resume_data.get('name', 'Resume').replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Failed to generate PDF.")
