import streamlit as st
import os
import json
import io
import pandas as pd
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from xhtml2pdf import pisa
from streamlit_gsheets import GSheetsConnection
import re

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
# 2. Enhanced HTML/CSS Resume Templates
# ==========================================
def get_base_styles():
    return """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .resume-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
            background: white;
        }
        .section {
            margin-bottom: 20px;
        }
        .section-title {
            font-size: 16px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid #000;
            padding-bottom: 5px;
            margin-bottom: 15px;
            color: #000;
        }
        .header {
            text-align: center;
            margin-bottom: 25px;
        }
        .name {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .contact {
            font-size: 12px;
            color: #666;
        }
        .experience-item, .project-item, .education-item {
            margin-bottom: 15px;
        }
        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 5px;
        }
        .item-title {
            font-weight: 600;
            font-size: 14px;
        }
        .item-subtitle {
            font-weight: 500;
            color: #444;
        }
        .item-date {
            font-size: 12px;
            color: #666;
            font-style: italic;
        }
        .item-description {
            font-size: 13px;
            color: #444;
            margin-left: 0;
            line-height: 1.5;
        }
        .skills-list {
            font-size: 13px;
            line-height: 1.6;
        }
        .bullet-point {
            margin-bottom: 3px;
            list-style-type: disc;
            margin-left: 20px;
        }
        @media print {
            .resume-container {
                padding: 20px;
            }
        }
    </style>
    """

def render_faang_template(data):
    # Filter out empty sections
    has_experience = data.get('experience') and len([e for e in data['experience'] if e.get('title') or e.get('company')]) > 0
    has_projects = data.get('projects') and len([p for p in data['projects'] if p.get('name')]) > 0
    has_education = data.get('education') and len([e for e in data['education'] if e.get('university') or e.get('degree')]) > 0
    has_skills = data.get('skills') and data['skills'].strip()
    has_summary = data.get('summary') and data['summary'].strip()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {get_base_styles()}
    </head>
    <body>
        <div class="resume-container">
            <!-- Header -->
            <div class="header">
                <div class="name">{data.get('name', 'Your Name')}</div>
                <div class="contact">{data.get('contact', '')}</div>
            </div>
    """
    
    # Summary (only if exists)
    if has_summary:
        html += f"""
            <div class="section">
                <div class="section-title">Professional Summary</div>
                <p class="item-description">{data.get('summary', '')}</p>
            </div>
        """
    
    # Experience (only if exists)
    if has_experience:
        html += f"""
            <div class="section">
                <div class="section-title">Professional Experience</div>
        """
        for exp in data.get('experience', []):
            if exp.get('title') or exp.get('company'):  # Only show if there's content
                html += f"""
                    <div class="experience-item">
                        <div class="item-header">
                            <div>
                                <span class="item-title">{exp.get('title', '')}</span>
                                {f'<span class="item-subtitle"> at {exp.get("company", "")}</span>' if exp.get('company') else ''}
                            </div>
                            <div class="item-date">{exp.get('duration', '')}</div>
                        </div>
                """
                if exp.get('description'):
                    # Split description into bullet points if it contains multiple sentences
                    desc = exp.get('description', '')
                    if '. ' in desc:
                        points = desc.split('. ')
                        for point in points:
                            if point.strip():
                                html += f'<div class="bullet-point">{point.strip()}{"." if not point.endswith(".") else ""}</div>'
                    else:
                        html += f'<div class="item-description">{desc}</div>'
                html += "</div>"
        html += "</div>"
    
    # Projects (only if exists)
    if has_projects:
        html += f"""
            <div class="section">
                <div class="section-title">Projects</div>
        """
        for proj in data.get('projects', []):
            if proj.get('name'):
                html += f"""
                    <div class="project-item">
                        <div class="item-header">
                            <span class="item-title">{proj.get('name', '')}</span>
                            {f'<span class="item-date">{proj.get("tech_stack", "")}</span>' if proj.get('tech_stack') else ''}
                        </div>
                """
                if proj.get('description'):
                    html += f'<div class="item-description">{proj.get("description", "")}</div>'
                html += "</div>"
        html += "</div>"
    
    # Education (only if exists)
    if has_education:
        html += f"""
            <div class="section">
                <div class="section-title">Education</div>
        """
        for edu in data.get('education', []):
            if edu.get('university') or edu.get('degree'):
                html += f"""
                    <div class="education-item">
                        <div class="item-header">
                            <div>
                                <span class="item-title">{edu.get('university', '')}</span>
                                {f'<span class="item-subtitle"> - {edu.get("degree", "")}</span>' if edu.get('degree') else ''}
                            </div>
                            <div class="item-date">{edu.get('year', '')}</div>
                        </div>
                    </div>
                """
        html += "</div>"
    
    # Skills (only if exists)
    if has_skills:
        html += f"""
            <div class="section">
                <div class="section-title">Skills</div>
                <div class="skills-list">{data.get('skills', '')}</div>
            </div>
        """
    
    html += """
        </div>
    </body>
    </html>
    """
    return html

def render_xyz_template(data):
    # Custom styles for XYZ template
    xyz_styles = """
    <style>
        .section-title {
            color: #2a75d3;
            border-bottom-color: #2a75d3;
        }
        .name {
            color: #2a75d3;
        }
        .item-title {
            color: #1a4b8c;
        }
        body {
            font-family: 'Georgia', serif;
        }
    </style>
    """
    
    html = render_faang_template(data)
    # Inject custom styles
    html = html.replace('</head>', f'{xyz_styles}</head>')
    return html

# ==========================================
# 3. Enhanced DOCX Generator
# ==========================================
def generate_docx(data):
    doc = Document()
    
    # Set document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
    
    # Name (centered)
    name = doc.add_heading(data.get('name', 'Your Name'), 0)
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Contact
    if data.get('contact'):
        contact = doc.add_paragraph(data.get('contact'))
        contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Helper function to add section only if content exists
    def add_section(title, content_func):
        if content_func():
            doc.add_heading(title, level=1)
            content_func()
    
    # Summary
    if data.get('summary', '').strip():
        doc.add_heading('Professional Summary', level=1)
        doc.add_paragraph(data.get('summary'))
    
    # Experience
    if data.get('experience') and any(e.get('title') or e.get('company') for e in data['experience']):
        doc.add_heading('Professional Experience', level=1)
        for exp in data['experience']:
            if exp.get('title') or exp.get('company'):
                p = doc.add_paragraph()
                p.add_run(exp.get('title', '')).bold = True
                if exp.get('company'):
                    p.add_run(f" at {exp.get('company')}")
                if exp.get('duration'):
                    p.add_run(f" | {exp.get('duration')}").italic = True
                
                if exp.get('description'):
                    # Add description with proper formatting
                    desc = exp.get('description')
                    if '. ' in desc:
                        points = desc.split('. ')
                        for point in points:
                            if point.strip():
                                bullet_para = doc.add_paragraph(style='List Bullet')
                                bullet_para.add_run(point.strip() + '.')
                    else:
                        doc.add_paragraph(desc)
    
    # Projects
    if data.get('projects') and any(p.get('name') for p in data['projects']):
        doc.add_heading('Projects', level=1)
        for proj in data['projects']:
            if proj.get('name'):
                p = doc.add_paragraph()
                p.add_run(proj.get('name', '')).bold = True
                if proj.get('tech_stack'):
                    p.add_run(f" | {proj.get('tech_stack')}").italic = True
                
                if proj.get('description'):
                    doc.add_paragraph(proj.get('description'), style='List Bullet' if len(proj.get('description')) < 100 else 'Normal')
    
    # Education
    if data.get('education') and any(e.get('university') or e.get('degree') for e in data['education']):
        doc.add_heading('Education', level=1)
        for edu in data['education']:
            if edu.get('university') or edu.get('degree'):
                p = doc.add_paragraph()
                title_run = p.add_run(edu.get('university', ''))
                title_run.bold = True
                if edu.get('degree'):
                    p.add_run(f" - {edu.get('degree')}")
                if edu.get('year'):
                    p.add_run(f" ({edu.get('year')})").italic = True
    
    # Skills
    if data.get('skills', '').strip():
        doc.add_heading('Skills', level=1)
        skills_para = doc.add_paragraph()
        skills_para.add_run(data.get('skills'))
    
    # Save to bytes
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ==========================================
# 4. Enhanced PDF Generator
# ==========================================
def generate_pdf(html_content):
    # Add print-specific styles
    print_styles = """
    <style>
        @page {
            size: A4;
            margin: 2.5cm;
        }
        body {
            background: white;
            font-size: 12pt;
        }
        .resume-container {
            max-width: 100%;
            padding: 0;
        }
        .section-title {
            font-size: 14pt;
        }
        .name {
            font-size: 24pt;
        }
    </style>
    """
    
    # Insert print styles before closing head
    full_html = html_content.replace('</head>', f'{print_styles}</head>')
    
    result = io.BytesIO()
    pdf = pisa.pisaDocument(
        io.BytesIO(full_html.encode("UTF-8")), 
        result,
        encoding='UTF-8'
    )
    
    if not pdf.err:
        return result.getvalue()
    return None

# ==========================================
# 5. Enhanced AI Processing
# ==========================================
def extract_details_with_ai(raw_text):
    prompt = """
    You are an expert resume writer and career coach. Extract and ENHANCE the information from the user's raw text.

    CRITICAL INSTRUCTIONS:
    1. ONLY include sections where the user has provided relevant information
    2. If a section has NO data, OMIT it completely from the JSON
    3. For incomplete information, generate professional, realistic content based on standard industry practices
    4. Write compelling bullet points (3-5) for each role/project that highlight achievements and impact
    5. Use action verbs and quantify results where possible
    6. Format skills as a clean, comma-separated list grouped by category
    7. Ensure all text is grammatically perfect and professional

    Output format: Return ONLY valid JSON with this structure (omit empty sections):
    {
        "name": "Full Name",
        "contact": "Email | Phone | Location | LinkedIn/GitHub (if provided)",
        "summary": "2-3 sentence professional summary (only if enough info exists)",
        "experience": [
            {
                "title": "Job Title",
                "company": "Company Name",
                "duration": "Start Date - End Date",
                "description": "Multiple bullet points separated by periods. Each bullet should be an achievement-oriented statement."
            }
        ],
        "projects": [
            {
                "name": "Project Name",
                "tech_stack": "Technologies used",
                "description": "Detailed project description with problem solved and impact"
            }
        ],
        "education": [
            {
                "degree": "Degree Name",
                "university": "University Name",
                "year": "Graduation Year"
            }
        ],
        "skills": "Technical Skills: Python, Java | Soft Skills: Leadership, Communication"
    }
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Clean up the result: remove empty sections
        cleaned_result = {}
        for key, value in result.items():
            if key in ['experience', 'projects', 'education']:
                # For list fields, only keep if there are items with content
                if value and isinstance(value, list):
                    non_empty_items = []
                    for item in value:
                        if any(str(v).strip() for v in item.values() if v):
                            non_empty_items.append(item)
                    if non_empty_items:
                        cleaned_result[key] = non_empty_items
            else:
                # For string fields, only keep if there's content
                if value and str(value).strip():
                    cleaned_result[key] = value
        
        return cleaned_result
        
    except Exception as e:
        st.error(f"Error communicating with OpenRouter API: {e}")
        return None

# ==========================================
# 6. Database Logging (Google Sheets)
# ==========================================
def save_name_to_sheets(name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(usecols=[0], ttl=0)
        new_row = pd.DataFrame({"Name": [name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(data=updated_df)
    except Exception:
        pass  # Fail silently

# ==========================================
# 7. Streamlit UI
# ==========================================
st.set_page_config(
    page_title="Resumed Pro | AI Resume Builder", 
    layout="wide", 
    page_icon="📄",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background-color: #2a75d3;
        color: white;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #1a4b8c;
    }
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

# Main Header
st.title("📄 Resumed Pro - AI-Powered Resume Builder")
st.markdown("Transform your raw experience into a professional, ATS-friendly resume in minutes.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    template_choice = st.selectbox(
        "Resume Template:",
        ["FAANG Template (Modern)", "XYZ Format (Professional)"],
        help="Choose the visual style for your resume"
    )
    
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
    1. **Paste** your raw experience in the text box
    2. **AI Enhancement** - Our AI writes professional bullet points and fills gaps
    3. **Preview** - See your formatted resume instantly
    4. **Export** - Download as Word or PDF with perfect formatting
    """)
    
    st.markdown("---")
    st.markdown("### Pro Tips")
    st.info("""
    • Include specific achievements and metrics
    • Mention technologies you've used
    • List both work experience and projects
    """)

# Initialize session state
if "resume_data" not in st.session_state:
    st.session_state.resume_data = None

# Create tabs
tab1, tab2 = st.tabs(["📝 Enter Details", "👁️ Preview & Export"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📋 Your Professional Background")
        st.caption("Paste your work experience, projects, education, and skills. Don't worry about formatting - we'll handle that!")
        
        raw_text = st.text_area(
            "Raw Experience Text:",
            height=300,
            placeholder="Example:\n\nWorked as a software engineer at Google for 3 years. Built scalable microservices using Python and Kubernetes. Improved API response time by 40%.\n\nCreated a machine learning project for sentiment analysis using BERT and PyTorch.\n\nBS in Computer Science from Stanford University, 2020.\n\nSkills: Python, Java, AWS, React, Machine Learning",
            help="The more details you provide, the better your resume will be!"
        )
        
        if st.button("✨ Generate Professional Resume", use_container_width=True):
            if raw_text.strip():
                with st.spinner("Analyzing your experience and crafting professional content..."):
                    result = extract_details_with_ai(raw_text)
                    if result:
                        st.session_state.resume_data = result
                        
                        if result.get("name"):
                            save_name_to_sheets(result["name"])
                        
                        st.success("✅ Your professional resume has been generated! Go to the Preview tab to see it.")
                        st.balloons()
            else:
                st.warning("Please paste your experience details first.")
    
    with col2:
        st.markdown("### 📊 What We'll Enhance")
        st.markdown("""
        ✓ **Professional Summaries** - Compelling overviews of your profile
        
        ✓ **Achievement Bullets** - Action-oriented descriptions with metrics
        
        ✓ **Skill Extraction** - Categorized technical and soft skills
        
        ✓ **Project Descriptions** - Impact-focused project highlights
        
        ✓ **Education Formatting** - Clean, consistent education section
        """)
        
        st.markdown("### 🔍 Example Input")
        with st.expander("See example"):
            st.code("""
Software developer at Microsoft (2021-2023). 
Worked on Azure cloud services. 
Built a dashboard for monitoring. 
Improved system reliability.

Created a React Native app for fitness tracking.
Used Firebase for backend.

MS in Computer Science from MIT, 2021.
Skills: JavaScript, Python, Azure, React
            """)

with tab2:
    if st.session_state.resume_data:
        data = st.session_state.resume_data
        
        # Export buttons
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        
        # Determine template
        template_map = {
            "FAANG Template (Modern)": render_faang_template,
            "XYZ Format (Professional)": render_xyz_template
        }
        render_func = template_map.get(template_choice, render_faang_template)
        final_html = render_func(data)
        
        with col1:
            docx_file = generate_docx(data)
            st.download_button(
                label="📄 Word",
                data=docx_file,
                file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        
        with col2:
            pdf_file = generate_pdf(final_html)
            if pdf_file:
                st.download_button(
                    label="📥 PDF",
                    data=pdf_file,
                    file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error("PDF generation failed")
        
        with col3:
            # JSON export for backup
            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="📋 JSON",
                data=json_str,
                file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # Preview section
        st.subheader("📱 Live Preview")
        st.caption("This is exactly how your resume will look when downloaded")
        
        with st.container(border=True):
            st.components.v1.html(final_html, height=800, scrolling=True)
        
        # Edit mode
        with st.expander("✏️ Edit Generated Content (Optional)"):
            st.warning("Make changes if needed - they'll reflect in the download")
            
            edited_data = data.copy()
            
            col1, col2 = st.columns(2)
            with col1:
                edited_data['name'] = st.text_input("Name", data.get('name', ''))
                edited_data['contact'] = st.text_input("Contact", data.get('contact', ''))
            
            with col2:
                edited_data['summary'] = st.text_area("Summary", data.get('summary', ''), height=100)
                edited_data['skills'] = st.text_area("Skills", data.get('skills', ''), height=80)
            
            if st.button("Update Preview"):
                st.session_state.resume_data = edited_data
                st.rerun()
    
    else:
        st.info("👈 Please enter your details and generate the resume in the first tab to see the preview here.")
        
        # Show placeholder
        st.markdown("""
        <div style="text-align: center; padding: 50px; background: #f8f9fa; border-radius: 10px;">
            <h3>🚀 No Resume Generated Yet</h3>
            <p>Go to the "Enter Details" tab and paste your experience to get started!</p>
        </div>
        """, unsafe_allow_html=True)
