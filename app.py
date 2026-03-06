import streamlit as st
import os
import json
import io
import pandas as pd
from openai import OpenAI
from docx import Document
from xhtml2pdf import pisa
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. API Configuration (OpenRouter)
# ==========================================
try:
    api_key = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
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
    html = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 30px; color: #000; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.1);">
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
# 3. AI Processing
# ==========================================
def extract_details_with_ai(raw_text):
    prompt = """
    You are an expert resume writer and career coach. Extract the information from the user's raw text and format it STRICTLY as a JSON object. 
    
    CRITICAL INSTRUCTIONS:
    1. If the user provides incomplete details, you MUST auto-generate a professional, realistic description with bullet points based on standard industry practices for that role.
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
# 4. File Export Generators 
# ==========================================
def generate_docx(data):
    doc = Document()
    name = doc.add_heading(data.get('name', 'Your Name'), 0)
    name.alignment = 1 
    contact = doc.add_paragraph(data.get('contact', ''))
    contact.alignment = 1
    doc.add_heading('Professional Summary', level=1)
    doc.add_paragraph(data.get('summary', ''))
    doc.add_heading('Experience', level=1)
    for exp in data.get('experience', []):
        p = doc.add_paragraph()
        p.add_run(exp.get('title', '')).bold = True
        p.add_run(f" at {exp.get('company', '')}")
        p.add_run(f" | {exp.get('duration', '')}").italic = True
        doc.add_paragraph(exp.get('description', ''))
    if data.get('projects'):
        doc.add_heading('Projects', level=1)
        for proj in data.get('projects', []):
            p = doc.add_paragraph()
            p.add_run(proj.get('name', '')).bold = True
            if proj.get('tech_stack'):
                p.add_run(f" | {proj.get('tech_stack', '')}").italic = True
            doc.add_paragraph(proj.get('description', ''))
    doc.add_heading('Education', level=1)
    for edu in data.get('education', []):
        p = doc.add_paragraph()
        p.add_run(edu.get('university', '')).bold = True
        p.add_run(f" - {edu.get('degree', '')} ({edu.get('year', '')})")
    doc.add_heading('Skills', level=1)
    doc.add_paragraph(data.get('skills', ''))
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(html_content):
    full_html = f"<html><body>{html_content}</body></html>"
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(full_html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

# ==========================================
# 5. Database Logging (Google Sheets)
# ==========================================
def save_name_to_sheets(name):
    """Silently attempts to save the generated name to a Google Sheet."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Read the existing data
        df = conn.read(usecols=[0], ttl=0) # Reads the first column
        # Append the new name
        new_row = pd.DataFrame({"Name": [name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        # Update the sheet
        conn.update(data=updated_df)
    except Exception as e:
        # Fail silently so the user still gets their resume even if Sheets isn't set up yet
        pass 

# ==========================================
# 6. Streamlit UI Elements (Enhanced)
# ==========================================
st.set_page_config(page_title="Resumed | AI Builder", layout="wide", page_icon="📄")

# Main Header
st.title("📄 Resumed - Build your resume with AI")
st.info("🚀 *This is base version, in next update : live interection with AI step by step*")

# Sidebar for Settings
with st.sidebar:
    st.header("⚙️ Configuration")
    template_choice = st.selectbox("Select Template Format:", ["FAANG Template", "XYZ Format"])
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("1. Dump your raw experience into the text box.\n2. AI organizes, expands, and formats it.\n3. Download as Word or PDF.")

# Initialize session state so data persists between tabs
if "resume_data" not in st.session_state:
    st.session_state.resume_data = None

# Create Interactive Tabs
tab1, tab2 = st.tabs(["📝 1. Enter Your Details", "👁️ 2. Preview & Export"])

with tab1:
    st.markdown("### Drop your raw background here")
    st.caption("💡 **Pro Tip:** Include your basic info, jobs, projects, and education. Don't worry about formatting—the AI will write professional bullet points and infer missing skills automatically!")
    
    raw_text = st.text_area("Experience & Projects:", height=250, placeholder="e.g., My name is John Doe. I worked at Google as a backend dev from 2021-2023. Built a scalable API... ")

    if st.button("✨ Generate & Enhance Resume", use_container_width=True):
        if raw_text.strip():
            with st.spinner("Analyzing data and generating professional descriptions..."):
                # 1. Generate the data
                result = extract_details_with_ai(raw_text)
                if result:
                    st.session_state.resume_data = result
                    
                    # 2. Save the name to Google Sheets silently
                    if result.get("name"):
                        save_name_to_sheets(result["name"])
                        
                    st.success("Resume generated successfully! Go to the 'Preview & Export' tab to view it.")
        else:
            st.warning("Please paste some text before generating.")

with tab2:
    if st.session_state.resume_data:
        data = st.session_state.resume_data
        
        # Action Buttons Row
        col1, col2, col3 = st.columns([1, 1, 2])
        
        # Prepare downloads
        if template_choice == "FAANG Template":
            final_html = render_faang_template(data)
        else:
            final_html = render_xyz_template(data)
            
        with col1:
            docx_file = generate_docx(data)
            st.download_button(
                label="📄 Download Word (.docx)",
                data=docx_file,
                file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        with col2:
            pdf_file = generate_pdf(final_html)
            if pdf_file:
                st.download_button(
                    label="📥 Download PDF (.pdf)",
                    data=pdf_file,
                    file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error("PDF Failed.")
                
        st.markdown("---")
        
        # Render Preview
        st.subheader("Live Preview")
        with st.container(border=True):
            st.components.v1.html(final_html, height=800, scrolling=True)
            
    else:
        st.info("👈 Please enter your details and generate the resume in the first tab to see the preview here.")
