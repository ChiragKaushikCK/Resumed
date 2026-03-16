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
from json_repair import repair_json

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
# 2. Advanced HTML/PDF Resume Templates (Enhanced CSS)
# ==========================================
def render_faang_template(data, is_pdf=False):
    """
    Clean, minimalist FAANG style. Uses HTML tables for xhtml2pdf alignment.
    Upgraded with modern paper-like CSS for the web view.
    """
    pdf_styles = "@page { margin: 0.75in; }" if is_pdf else ""
    
    # Elegant paper shadow and padding for the live web preview
    wrapper_style = "" if is_pdf else """
        max-width: 850px; 
        margin: 20px auto; 
        padding: 60px; 
        background: white; 
        box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.15); 
        border-radius: 4px;
    """

    html = f"""
    <html>
    <head>
    <style>
        {pdf_styles}
        body {{ 
            font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; 
            color: #1a1a1a; 
            font-size: 13px; 
            line-height: 1.5; 
            background-color: #f4f4f9; /* Soft background outside the paper */
        }}
        h1 {{ 
            font-size: 32px; 
            text-align: center; 
            margin: 0 0 8px 0; 
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .contact {{ 
            text-align: center; 
            color: #555; 
            font-size: 12px; 
            margin-bottom: 20px; 
        }}
        .section-title {{ 
            border-bottom: 2px solid #333; 
            padding-bottom: 4px; 
            margin-top: 24px; 
            margin-bottom: 12px; 
            text-transform: uppercase; 
            font-size: 14px; 
            font-weight: 800; 
            letter-spacing: 0.5px;
        }}
        .item-table {{ width: 100%; margin-top: 12px; border-collapse: collapse; }}
        .item-table td {{ padding: 0; vertical-align: bottom; }}
        .desc {{ margin-top: 6px; font-size: 12px; color: #333; }}
        .desc ul {{ margin-top: 4px; padding-left: 20px; }}
        .desc li {{ margin-bottom: 4px; }}
    </style>
    </head>
    <body>
    <div style="{wrapper_style}">
        <h1>{data.get('name', 'Your Name')}</h1>
        <div class="contact">{data.get('contact', 'Email | Phone | LinkedIn')}</div>
    """

    if data.get('summary'):
        html += f"""
        <div class="section-title">Professional Summary</div>
        <p style="margin-top: 0; font-size: 12px; color: #333;">{data['summary']}</p>
        """

    if data.get('experience') and len(data['experience']) > 0:
        html += '<div class="section-title">Experience</div>'
        for exp in data['experience']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b style="font-size: 14px;">{exp.get('title', '')}</b> | {exp.get('company', '')}</td>
                    <td align="right" style="color: #666; font-weight: 500;">{exp.get('duration', '')}</td>
                </tr>
            </table>
            <div class="desc">{exp.get('description', '')}</div>
            """

    if data.get('projects') and len(data['projects']) > 0:
        html += '<div class="section-title">Projects</div>'
        for proj in data['projects']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b style="font-size: 14px;">{proj.get('name', '')}</b></td>
                    <td align="right" style="color: #666; font-weight: 500;">{proj.get('tech_stack', '')}</td>
                </tr>
            </table>
            <div class="desc">{proj.get('description', '')}</div>
            """

    if data.get('education') and len(data['education']) > 0:
        html += '<div class="section-title">Education</div>'
        for edu in data['education']:
            html += f"""
            <table class="item-table">
                <tr>
                    <td align="left"><b style="font-size: 14px;">{edu.get('university', '')}</b><br>{edu.get('degree', '')}</td>
                    <td align="right" style="color: #666; font-weight: 500; vertical-align: top;">{edu.get('year', '')}</td>
                </tr>
            </table>
            """

    if data.get('skills'):
        html += f"""
        <div class="section-title">Skills</div>
        <p style="margin-top: 0; font-size: 12px; color: #333;">{data['skills']}</p>
        """

    html += "</div></body></html>"
    return html

def render_xyz_template(data, is_pdf=False):
    """
    Elegant Serif style with dark blue accents.
    """
    html = render_faang_template(data, is_pdf).replace(
        "font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;", 
        "font-family: 'Georgia', serif;"
    ).replace(
        "border-bottom: 2px solid #333;", 
        "border-bottom: 2px solid #1a5276;" # Elegant Dark Blue
    ).replace(
        "text-transform: uppercase;",
        "color: #1a5276; text-transform: uppercase;"
    ).replace(
        "color: #1a1a1a;",
        "color: #2c3e50;"
    )
    return html

# ==========================================
# 3. AI Processing (Live Visual Streaming)
# ==========================================
def extract_details_with_ai(raw_text, ui_placeholder, template_choice):
    prompt = """
    You are an expert resume writer and career coach. Extract the information from the user's raw text and format it STRICTLY as a JSON object. 
    
    CRITICAL INSTRUCTIONS:
    1. Only include sections the user provides data for. If no education is mentioned, leave the array EMPTY.
    2. Auto-generate professional, realistic descriptions based on standard industry practices for that role if the user's text is brief. USE HTML BULLET POINTS (<ul><li>...</li></ul>) for the descriptions to make them look great.
    3. Infer relevant skills.
    4. Ensure all descriptions are highly professional and action-oriented.
    5. Return ONLY valid JSON.
    
    Required JSON Schema:
    {
        "name": "Full Name",
        "contact": "Email | Phone | Location / Links",
        "summary": "A strong 2-3 sentence professional summary.",
        "experience": [{"title": "Job", "company": "Company", "duration": "Dates", "description": "<ul><li>Bullet point</li></ul>"}],
        "projects": [{"name": "Project", "tech_stack": "Tech", "description": "Details"}],
        "education": [{"degree": "Degree", "university": "Uni", "year": "Year"}],
        "skills": "Comma-separated skills"
    }
    """
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            stream=True 
        )
        
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content
                
                try:
                    partial_data = repair_json(full_response, return_objects=True)
                    
                    if isinstance(partial_data, dict):
                        if template_choice == "FAANG Template":
                            live_html = render_faang_template(partial_data, is_pdf=False)
                        else:
                            live_html = render_xyz_template(partial_data, is_pdf=False)
                            
                        # Stream the HTML directly. The CSS will make it look like a building sheet of paper.
                        ui_placeholder.markdown(live_html, unsafe_allow_html=True)
                except Exception:
                    pass # Skip frames where JSON repair temporarily fails
        
        return repair_json(full_response, return_objects=True)

    except Exception as e:
        st.error(f"Error communicating with OpenRouter API: {e}")
        return None

# ==========================================
# 4. Advanced File Export Generators 
# ==========================================
def generate_docx(data):
    doc = Document()
    for section in doc.sections:
        section.top_margin, section.bottom_margin = Inches(0.75), Inches(0.75)
        section.left_margin, section.right_margin = Inches(0.75), Inches(0.75)

    def add_section_header(text):
        p = doc.add_paragraph()
        run = p.add_run(text.upper())
        run.bold, run.font.size = True, Pt(11)
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(14), Pt(4)

    def add_split_header(left_bold, left_regular, right_text):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(7.0), WD_TAB_ALIGNMENT.RIGHT)
        run_bold = p.add_run(left_bold)
        run_bold.bold = True
        if left_regular: p.add_run(f" | {left_regular}")
        if right_text: p.add_run(f"\t{right_text}") 

    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_p.add_run(data.get('name', 'Your Name'))
    name_run.bold, name_run.font.size = True, Pt(22)
    name_p.paragraph_format.space_after = Pt(2)

    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_run = contact_p.add_run(data.get('contact', ''))
    contact_run.font.size = Pt(10)
    contact_p.paragraph_format.space_after = Pt(10)

    if data.get('summary'):
        add_section_header('Professional Summary')
        p = doc.add_paragraph(data.get('summary', ''))
        p.paragraph_format.space_after = Pt(6)

    # Simplified stripping of HTML tags for Word doc since we told AI to use <ul><li>
    import re
    def clean_html(raw_html):
        cleanr = re.compile('<.*?>')
        return re.sub(cleanr, '', raw_html)

    if data.get('experience'):
        add_section_header('Experience')
        for exp in data['experience']:
            add_split_header(exp.get('title', ''), exp.get('company', ''), exp.get('duration', ''))
            p = doc.add_paragraph(clean_html(exp.get('description', '')))
            p.paragraph_format.space_after = Pt(8)

    if data.get('projects'):
        add_section_header('Projects')
        for proj in data['projects']:
            add_split_header(proj.get('name', ''), "", proj.get('tech_stack', ''))
            p = doc.add_paragraph(clean_html(proj.get('description', '')))
            p.paragraph_format.space_after = Pt(8)

    if data.get('education'):
        add_section_header('Education')
        for edu in data['education']:
            add_split_header(edu.get('university', ''), "", edu.get('year', ''))
            p = doc.add_paragraph(edu.get('degree', ''))
            p.paragraph_format.space_after = Pt(6)

    if data.get('skills'):
        add_section_header('Skills')
        doc.add_paragraph(data.get('skills', ''))

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(html_content):
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html_content.encode("UTF-8")), result)
    if not pdf.err: return result.getvalue()
    return None

# ==========================================
# 5. Database Logging
# ==========================================
def save_name_to_sheets(name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(usecols=[0], ttl=0) 
        new_row = pd.DataFrame({"Name": [name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(data=updated_df)
    except Exception:
        pass 

# ==========================================
# 6. Streamlit UI Elements
# ==========================================
st.set_page_config(page_title="Resumed | AI Builder", layout="wide", page_icon="📄")

# Inject global background styling for Streamlit
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

st.title("📄 Resumed - Live AI Builder")

with st.sidebar:
    st.header("⚙️ Configuration")
    template_choice = st.selectbox("Select Template Format:", ["FAANG Template", "XYZ Format"])
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("1. Dump your raw experience.\n2. Watch the AI build your resume live.\n3. Download perfectly aligned Word/PDF files.")

if "resume_data" not in st.session_state:
    st.session_state.resume_data = None

tab1, tab2 = st.tabs(["📝 1. Enter Your Details", "👁️ 2. Export & Download"])

with tab1:
    st.markdown("### Drop your raw background here")
    raw_text = st.text_area("Experience & Projects:", height=200, placeholder="e.g., My name is John Doe. I worked at Google as a backend dev from 2021-2023...")

    if st.button("✨ Generate & Watch it Build", use_container_width=True):
        if raw_text.strip():
            st.markdown("### 🪄 Building your resume live...")
            
            # This is the container where the visual magic happens
            live_preview_container = st.empty() 
            
            result = extract_details_with_ai(raw_text, live_preview_container, template_choice)
            
            if result:
                st.session_state.resume_data = result
                if result.get("name"):
                    save_name_to_sheets(result["name"])
                
                st.success("✅ Resume complete! Go to the 'Export & Download' tab to get your files.")
        else:
            st.warning("Please paste some text before generating.")

with tab2:
    if st.session_state.resume_data:
        data = st.session_state.resume_data
        
        col1, col2 = st.columns(2)
        
        if template_choice == "FAANG Template":
            pdf_html = render_faang_template(data, is_pdf=True)
            final_preview = render_faang_template(data, is_pdf=False)
        else:
            pdf_html = render_xyz_template(data, is_pdf=True)
            final_preview = render_xyz_template(data, is_pdf=False)
            
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
            pdf_file = generate_pdf(pdf_html)
            if pdf_file:
                st.download_button(
                    label="📥 Download PDF (.pdf)",
                    data=pdf_file,
                    file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
        st.markdown("---")
        st.subheader("Final Review")
        st.components.v1.html(final_preview, height=900, scrolling=True)
            
    else:
        st.info("👈 Please enter your details in the first tab to generate your resume.")
