import streamlit as st
import os
import json
import io
import pandas as pd
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
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
# 2. Advanced HTML/PDF Resume Templates
# ==========================================
def render_faang_template(data, is_pdf=False):
    """
    Uses HTML tables for perfectly reliable alignment in xhtml2pdf exports.
    Conditionally renders sections only if data exists.
    """
    # Base CSS. For PDF, we set physical page margins.
    pdf_styles = "@page { margin: 0.75in; }" if is_pdf else ""
    wrapper_style = "" if is_pdf else "max-width: 800px; margin: 0 auto; padding: 40px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.1);"

    html = f"""
    <html>
    <head>
    <style>
        {pdf_styles}
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #000; font-size: 12px; line-height: 1.4; }}
        h1 {{ font-size: 28px; text-align: center; margin: 0 0 5px 0; }}
        .contact {{ text-align: center; color: #333; font-size: 11px; margin-bottom: 15px; border-bottom: 2px solid #000; padding-bottom: 10px; }}
        .section-title {{ border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; margin-bottom: 5px; text-transform: uppercase; font-size: 13px; font-weight: bold; }}
        .item-table {{ width: 100%; margin-top: 8px; border-collapse: collapse; }}
        .item-table td {{ padding: 0; vertical-align: bottom; }}
        .desc {{ margin-top: 3px; font-size: 11px; }}
    </style>
    </head>
    <body>
    <div style="{wrapper_style}">
        <h1>{data.get('name', 'Your Name')}</h1>
        <div class="contact">{data.get('contact', 'Email | Phone | LinkedIn')}</div>
    """

    # --- DYNAMIC: Summary ---
    if data.get('summary'):
        html += f"""
        <div class="section-title">Professional Summary</div>
        <p style="margin-top: 0; font-size: 11px;">{data['summary']}</p>
        """

    # --- DYNAMIC: Experience ---
    if data.get('experience') and len(data['experience']) > 0:
        html += '<div class="section-title">Experience</div>'
        for exp in data['experience']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b>{exp.get('title', '')}</b> at {exp.get('company', '')}</td>
                    <td align="right" style="color: #555;">{exp.get('duration', '')}</td>
                </tr>
            </table>
            <div class="desc">{exp.get('description', '')}</div>
            """

    # --- DYNAMIC: Projects ---
    if data.get('projects') and len(data['projects']) > 0:
        html += '<div class="section-title">Projects</div>'
        for proj in data['projects']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b>{proj.get('name', '')}</b></td>
                    <td align="right" style="color: #555;">{proj.get('tech_stack', '')}</td>
                </tr>
            </table>
            <div class="desc">{proj.get('description', '')}</div>
            """

    # --- DYNAMIC: Education ---
    if data.get('education') and len(data['education']) > 0:
        html += '<div class="section-title">Education</div>'
        for edu in data['education']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b>{edu.get('university', '')}</b><br>{edu.get('degree', '')}</td>
                    <td align="right" style="color: #555;">{edu.get('year', '')}</td>
                </tr>
            </table>
            """

    # --- DYNAMIC: Skills ---
    if data.get('skills'):
        html += f"""
        <div class="section-title">Skills</div>
        <p style="margin-top: 0; font-size: 11px;">{data['skills']}</p>
        """

    html += "</div></body></html>"
    return html

def render_xyz_template(data, is_pdf=False):
    html = render_faang_template(data, is_pdf).replace(
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
    1. Only include sections the user provides data for. If there is no mention of education, leave the education array EMPTY. Do not make up companies or universities.
    2. If the user provides incomplete details for an actual job, auto-generate a professional, realistic description based on standard industry practices for that role.
    3. Infer relevant skills if implied by the experience.
    4. Ensure all descriptions are highly professional and action-oriented.
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
# 4. Advanced File Export Generators 
# ==========================================
def generate_docx(data):
    """Generates a highly formatted MS Word document with custom margins and tab stops."""
    doc = Document()
    
    # Set narrow margins (0.75 inches)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Helper function for section headers
    def add_section_header(text):
        p = doc.add_paragraph()
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)

    # Helper function for left/right aligned headers (Job Title + Date)
    def add_split_header(left_bold, left_regular, right_text):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        # Add a right-aligned tab stop at 7 inches (Standard page width - margins)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(7.0), WD_TAB_ALIGNMENT.RIGHT)
        
        run_bold = p.add_run(left_bold)
        run_bold.bold = True
        if left_regular:
            p.add_run(f" {left_regular}")
        if right_text:
            p.add_run(f"\t{right_text}") # The \t pushes it to the right tab stop

    # Build Document
    # Name
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_p.add_run(data.get('name', 'Your Name'))
    name_run.bold = True
    name_run.font.size = Pt(22)
    name_p.paragraph_format.space_after = Pt(2)

    # Contact
    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_run = contact_p.add_run(data.get('contact', ''))
    contact_run.font.size = Pt(10)
    contact_p.paragraph_format.space_after = Pt(10)

    # Dynamic Sections
    if data.get('summary'):
        add_section_header('Professional Summary')
        p = doc.add_paragraph(data.get('summary', ''))
        p.paragraph_format.space_after = Pt(6)

    if data.get('experience') and len(data['experience']) > 0:
        add_section_header('Experience')
        for exp in data['experience']:
            add_split_header(exp.get('title', ''), f"at {exp.get('company', '')}", exp.get('duration', ''))
            p = doc.add_paragraph(exp.get('description', ''))
            p.paragraph_format.space_after = Pt(8)

    if data.get('projects') and len(data['projects']) > 0:
        add_section_header('Projects')
        for proj in data['projects']:
            add_split_header(proj.get('name', ''), "", proj.get('tech_stack', ''))
            p = doc.add_paragraph(proj.get('description', ''))
            p.paragraph_format.space_after = Pt(8)

    if data.get('education') and len(data['education']) > 0:
        add_section_header('Education')
        for edu in data['education']:
            add_split_header(edu.get('university', ''), "", edu.get('year', ''))
            p = doc.add_paragraph(edu.get('degree', ''))
            p.paragraph_format.space_after = Pt(6)

    if data.get('skills'):
        add_section_header('Skills')
        p = doc.add_paragraph(data.get('skills', ''))

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(html_content):
    """Converts the perfectly structured HTML table layout into a PDF."""
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html_content.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

# ==========================================
# 5. Database Logging (Google Sheets)
# ==========================================
def save_name_to_sheets(name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(usecols=[0], ttl=0) 
        new_row = pd.DataFrame({"Name": [name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(data=updated_df)
    except Exception as e:
        pass 

# ==========================================
# 6. Streamlit UI Elements
# ==========================================
st.set_page_config(page_title="Resumed | AI Builder", layout="wide", page_icon="📄")

st.title("📄 Resumed - Build your resume with AI")
st.info("🚀 *This is base version, in next update : live interection with AI step by step*")

with st.sidebar:
    st.header("⚙️ Configuration")
    template_choice = st.selectbox("Select Template Format:", ["FAANG Template", "XYZ Format"])
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("1. Dump your raw experience into the text box.\n2. AI organizes, expands, and formats it.\n3. Download as perfectly aligned Word or PDF files.")

if "resume_data" not in st.session_state:
    st.session_state.resume_data = None

tab1, tab2 = st.tabs(["📝 1. Enter Your Details", "👁️ 2. Preview & Export"])

with tab1:
    st.markdown("### Drop your raw background here")
    st.caption("💡 **Pro Tip:** Include your basic info, jobs, projects, and education. Don't worry about formatting—the AI will write professional bullet points and infer missing skills automatically!")
    
    raw_text = st.text_area("Experience & Projects:", height=250, placeholder="e.g., My name is John Doe. I worked at Google as a backend dev from 2021-2023. Built a scalable API... ")

    if st.button("✨ Generate & Enhance Resume", use_container_width=True):
        if raw_text.strip():
            with st.spinner("Analyzing data and generating professional descriptions..."):
                result = extract_details_with_ai(raw_text)
                if result:
                    st.session_state.resume_data = result
                    
                    if result.get("name"):
                        save_name_to_sheets(result["name"])
                        
                    st.success("Resume generated successfully! Go to the 'Preview & Export' tab to view it.")
        else:
            st.warning("Please paste some text before generating.")

with tab2:
    if st.session_state.resume_data:
        data = st.session_state.resume_data
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        # We generate two versions of the HTML: one styled for the web preview, one optimized for the PDF engine.
        if template_choice == "FAANG Template":
            preview_html = render_faang_template(data, is_pdf=False)
            pdf_html = render_faang_template(data, is_pdf=True)
        else:
            preview_html = render_xyz_template(data, is_pdf=False)
            pdf_html = render_xyz_template(data, is_pdf=True)
            
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
            # We feed the specialized pdf_html to the converter
            pdf_file = generate_pdf(pdf_html)
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
        
        st.subheader("Live Preview")
        # We display the web-optimized HTML here
        st.components.v1.html(preview_html, height=800, scrolling=True)
            
    else:
        st.info("👈 Please enter your details and generate the resume in the first tab to see the preview here.")
