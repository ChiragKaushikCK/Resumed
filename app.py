import streamlit as st
import os
import json
import io
import pandas as pd
import time
import random
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from xhtml2pdf import pisa
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

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
# 2. Advanced HTML/PDF Resume Templates with Live Preview
# ==========================================
def render_live_template(data, is_pdf=False, animation_stage=100):
    """
    Renders template with optional animation effects based on completion stage
    """
    pdf_styles = "@page { margin: 0.75in; }" if is_pdf else ""
    wrapper_style = "" if is_pdf else "max-width: 800px; margin: 0 auto; padding: 40px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.1);"
    
    # Add animation styles for live preview
    animation_css = """
    @keyframes typing {
        from { width: 0; opacity: 0; }
        to { width: 100%; opacity: 1; }
    }
    @keyframes fadeInLine {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .typing-animation {
        overflow: hidden;
        white-space: nowrap;
        animation: typing 1s steps(40, end);
        display: inline-block;
    }
    .line-fade {
        animation: fadeInLine 0.5s ease-out;
    }
    .highlight-new {
        background: linear-gradient(120deg, #f8ffae 0%, #f8ffae 100%);
        background-repeat: no-repeat;
        background-size: 100% 40%;
        background-position: 0 85%;
        transition: background-size 0.3s ease;
    }
    """
    
    html = f"""
    <html>
    <head>
    <style>
        {pdf_styles}
        {animation_css}
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #000; font-size: 12px; line-height: 1.4; }}
        h1 {{ font-size: 28px; text-align: center; margin: 0 0 5px 0; }}
        .contact {{ text-align: center; color: #333; font-size: 11px; margin-bottom: 15px; border-bottom: 2px solid #000; padding-bottom: 10px; }}
        .section-title {{ border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-top: 15px; margin-bottom: 5px; text-transform: uppercase; font-size: 13px; font-weight: bold; }}
        .item-table {{ width: 100%; margin-top: 8px; border-collapse: collapse; }}
        .item-table td {{ padding: 0; vertical-align: bottom; }}
        .desc {{ margin-top: 3px; font-size: 11px; }}
        .progress-overlay {{ 
            position: relative; 
            overflow: hidden;
        }}
        .progress-overlay::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: {animation_stage}%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }}
        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}
    </style>
    </head>
    <body>
    <div style="{wrapper_style}" class="progress-overlay">
        <h1 class="line-fade">{data.get('name', 'Your Name')}</h1>
        <div class="contact line-fade">{data.get('contact', 'Email | Phone | LinkedIn')}</div>
    """

    # Dynamic sections with progressive reveal
    sections = [
        ('summary', 'Professional Summary', data.get('summary', '')),
        ('experience', 'Experience', data.get('experience', [])),
        ('projects', 'Projects', data.get('projects', [])),
        ('education', 'Education', data.get('education', [])),
        ('skills', 'Skills', data.get('skills', ''))
    ]
    
    for i, (section_type, title, content) in enumerate(sections):
        # Only show sections based on animation stage
        if i * 20 <= animation_stage:
            if section_type == 'summary' and content:
                html += f"""
                <div class="section-title line-fade" style="animation-delay: {i*0.2}s">{title}</div>
                <p class="desc typing-animation" style="animation-delay: {i*0.2}s">{content}</p>
                """
            elif section_type == 'experience' and content:
                html += f'<div class="section-title line-fade" style="animation-delay: {i*0.2}s">{title}</div>'
                for j, exp in enumerate(content[:max(1, int(len(content) * animation_stage/100))]):
                    html += f"""
                    <table class="item-table line-fade" style="animation-delay: {i*0.2 + j*0.1}s">
                        <tr>
                            <td align="left"><b>{exp.get('title', '')}</b> at {exp.get('company', '')}</td>
                            <td align="right" style="color: #555;">{exp.get('duration', '')}</td>
                        </tr>
                    </table>
                    <div class="desc typing-animation" style="animation-delay: {i*0.2 + j*0.1}s">{exp.get('description', '')}</div>
                    """
            elif section_type == 'projects' and content:
                html += f'<div class="section-title line-fade" style="animation-delay: {i*0.2}s">{title}</div>'
                for j, proj in enumerate(content[:max(1, int(len(content) * animation_stage/100))]):
                    html += f"""
                    <table class="item-table line-fade" style="animation-delay: {i*0.2 + j*0.1}s">
                        <tr>
                            <td align="left"><b>{proj.get('name', '')}</b></td>
                            <td align="right" style="color: #555;">{proj.get('tech_stack', '')}</td>
                        </tr>
                    </table>
                    <div class="desc typing-animation" style="animation-delay: {i*0.2 + j*0.1}s">{proj.get('description', '')}</div>
                    """
            elif section_type == 'education' and content:
                html += f'<div class="section-title line-fade" style="animation-delay: {i*0.2}s">{title}</div>'
                for j, edu in enumerate(content[:max(1, int(len(content) * animation_stage/100))]):
                    html += f"""
                    <table class="item-table line-fade" style="animation-delay: {i*0.2 + j*0.1}s">
                        <tr>
                            <td align="left"><b>{edu.get('university', '')}</b><br>{edu.get('degree', '')}</td>
                            <td align="right" style="color: #555;">{edu.get('year', '')}</td>
                        </tr>
                    </table>
                    """
            elif section_type == 'skills' and content:
                html += f"""
                <div class="section-title line-fade" style="animation-delay: {i*0.2}s">{title}</div>
                <p class="desc typing-animation" style="animation-delay: {i*0.2}s">{content}</p>
                """

    html += "</div></body></html>"
    return html

# ==========================================
# 3. AI Processing with Live Streaming
# ==========================================
def stream_resume_generation(raw_text, placeholder):
    """
    Streams the resume generation process word by word with visual feedback
    """
    prompt = """
    You are an expert resume writer. Create a professional resume from the user's input.
    Return STRICT JSON format with these sections: name, contact, summary, experience, projects, education, skills.
    For each section, make descriptions detailed and achievement-oriented.
    """
    
    full_response = ""
    word_count = 0
    words_to_show = 50  # Show words progressively
    
    try:
        # Simulate streaming by chunking the response
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            response_format={"type": "json_object"},
            stream=True  # Enable streaming
        )
        
        collected_chunks = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                collected_chunks.append(content)
                full_response = ''.join(collected_chunks)
                
                # Try to parse JSON progressively
                try:
                    # Update placeholder with current state
                    word_count += len(content.split())
                    if word_count % 10 == 0:  # Update every 10 words
                        # Show partial JSON with visual feedback
                        progress = min(100, (word_count / words_to_show) * 100)
                        placeholder.markdown(f"""
                        <div style="background: #f0f2f6; border-radius: 10px; padding: 20px;">
                            <div style="color: #0f52ba; font-family: monospace; white-space: pre-wrap;">
                                ⚡ Generating your resume... {int(progress)}%
                                <div style="width: 100%; height: 4px; background: #e0e0e0; border-radius: 2px; margin: 10px 0;">
                                    <div style="width: {progress}%; height: 100%; background: #0f52ba; border-radius: 2px; transition: width 0.3s;"></div>
                                </div>
                                <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto;">
{full_response[:500]}{'...' if len(full_response) > 500 else ''}
                                </pre>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        time.sleep(0.1)
                except:
                    pass
        
        return json.loads(full_response)
        
    except Exception as e:
        st.error(f"Error in generation: {e}")
        return None

def extract_details_with_ai(raw_text, progress_bar, status_text, preview_placeholder):
    """
    Enhanced version with live preview updates during generation
    """
    prompt = """
    You are an expert resume writer and career coach. Extract and enhance the information from the user's raw text.
    Format STRICTLY as JSON with these sections.
    Make descriptions professional, achievement-oriented, and detailed.
    
    Required JSON Schema:
    {
        "name": "Full Name",
        "contact": "Email | Phone | Location / Links",
        "summary": "A strong 2-3 sentence professional summary with achievements and key strengths.",
        "experience": [
            {
                "title": "Job Title",
                "company": "Company Name",
                "duration": "Start Date - End Date",
                "description": "3-4 bullet points with achievements, metrics, and impact."
            }
        ],
        "projects": [
            {
                "name": "Project Name",
                "tech_stack": "Technologies used",
                "description": "2-3 bullet points describing the project, your role, and outcomes."
            }
        ],
        "education": [
            {
                "degree": "Degree Name",
                "university": "University Name",
                "year": "Graduation Year"
            }
        ],
        "skills": "Comma-separated list of technical and soft skills (15-20 skills)"
    }
    """
    
    try:
        status_text.text("🔄 Analyzing your experience...")
        progress_bar.progress(10)
        time.sleep(0.5)
        
        status_text.text("📝 Structuring your information...")
        progress_bar.progress(30)
        
        # Show a sample template while generating
        preview_placeholder.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 20px; color: white;">
            <h3 style="margin:0">✨ Building your resume...</h3>
            <p>Creating professional bullet points and achievements based on your experience</p>
            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <div style="flex:1; background: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px;">
                    <small>📊 Quantifying achievements</small>
                </div>
                <div style="flex:1; background: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px;">
                    <small>🎯 Adding impact metrics</small>
                </div>
                <div style="flex:1; background: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px;">
                    <small>🔍 Identifying key skills</small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Actual API call with streaming
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            response_format={"type": "json_object"}
        )
        
        progress_bar.progress(70)
        status_text.text("🎨 Formatting and enhancing content...")
        time.sleep(0.5)
        
        result = json.loads(response.choices[0].message.content)
        
        progress_bar.progress(90)
        status_text.text("✨ Finalizing your professional resume...")
        time.sleep(0.5)
        
        progress_bar.progress(100)
        status_text.text("✅ Resume ready!")
        time.sleep(0.5)
        
        return result
        
    except Exception as e:
        st.error(f"Error communicating with OpenRouter API: {e}")
        return None

# ==========================================
# 4. Enhanced Export Generators 
# ==========================================
def generate_docx(data):
    """Generates a highly formatted MS Word document"""
    doc = Document()
    
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    def add_section_header(text):
        p = doc.add_paragraph()
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)

    def add_split_header(left_bold, left_regular, right_text):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(7.0), WD_TAB_ALIGNMENT.RIGHT)
        
        run_bold = p.add_run(left_bold)
        run_bold.bold = True
        if left_regular:
            p.add_run(f" {left_regular}")
        if right_text:
            p.add_run(f"\t{right_text}")

    # Build Document
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_p.add_run(data.get('name', 'Your Name'))
    name_run.bold = True
    name_run.font.size = Pt(22)
    name_p.paragraph_format.space_after = Pt(2)

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
            # Split description into bullet points if they exist
            desc = exp.get('description', '')
            if '•' in desc:
                for line in desc.split('•'):
                    if line.strip():
                        p = doc.add_paragraph(line.strip(), style='List Bullet')
                        p.paragraph_format.space_after = Pt(2)
            else:
                p = doc.add_paragraph(desc)
                p.paragraph_format.space_after = Pt(8)

    if data.get('projects') and len(data['projects']) > 0:
        add_section_header('Projects')
        for proj in data['projects']:
            add_split_header(proj.get('name', ''), "", proj.get('tech_stack', ''))
            desc = proj.get('description', '')
            if '•' in desc:
                for line in desc.split('•'):
                    if line.strip():
                        p = doc.add_paragraph(line.strip(), style='List Bullet')
                        p.paragraph_format.space_after = Pt(2)
            else:
                p = doc.add_paragraph(desc)
                p.paragraph_format.space_after = Pt(8)

    if data.get('education') and len(data['education']) > 0:
        add_section_header('Education')
        for edu in data['education']:
            add_split_header(edu.get('university', ''), "", edu.get('year', ''))
            p = doc.add_paragraph(edu.get('degree', ''))
            p.paragraph_format.space_after = Pt(6)

    if data.get('skills'):
        add_section_header('Skills')
        # Format skills in columns
        skills = data.get('skills', '').split(',')
        skills_text = ''
        for i, skill in enumerate(skills):
            skills_text += skill.strip()
            if (i + 1) % 5 == 0:
                skills_text += '\n'
            elif i < len(skills) - 1:
                skills_text += ' • '
        p = doc.add_paragraph(skills_text)

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(html_content):
    """Converts HTML to PDF"""
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
# 6. Interactive UI Components
# ==========================================
def create_interactive_editor(data):
    """
    Creates an interactive editor where users can modify each section live
    """
    st.subheader("✏️ Live Editor - Click to Edit Any Section")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Name editor
        new_name = st.text_input("Full Name", value=data.get('name', ''), key='name_edit')
        if new_name != data.get('name'):
            data['name'] = new_name
            
        # Contact editor
        new_contact = st.text_input("Contact Info", value=data.get('contact', ''), key='contact_edit')
        if new_contact != data.get('contact'):
            data['contact'] = new_contact
    
    with col2:
        st.markdown("""
        <div style="background: #e8f4fd; padding: 15px; border-radius: 10px;">
            <h4 style="margin:0">💡 Pro Tip</h4>
            <p style="font-size: 12px; margin-top:5px">Edit any section in real-time and see the preview update instantly!</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Summary editor
    st.markdown("#### Professional Summary")
    new_summary = st.text_area("Edit Summary", value=data.get('summary', ''), height=100, key='summary_edit')
    if new_summary != data.get('summary'):
        data['summary'] = new_summary
    
    # Experience editor
    st.markdown("#### Experience")
    if data.get('experience'):
        for i, exp in enumerate(data['experience']):
            with st.expander(f"{exp.get('title', '')} at {exp.get('company', '')}", expanded=i==0):
                col1, col2, col3 = st.columns(3)
                with col1:
                    exp['title'] = st.text_input("Title", value=exp.get('title', ''), key=f'title_{i}')
                with col2:
                    exp['company'] = st.text_input("Company", value=exp.get('company', ''), key=f'company_{i}')
                with col3:
                    exp['duration'] = st.text_input("Duration", value=exp.get('duration', ''), key=f'duration_{i}')
                exp['description'] = st.text_area("Description", value=exp.get('description', ''), height=100, key=f'desc_{i}')
    
    return data

# ==========================================
# 7. Main Streamlit App
# ==========================================
st.set_page_config(
    page_title="Resumed | Live Interactive Resume Builder", 
    layout="wide", 
    page_icon="✨",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 25px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .css-1d391kg {
        padding: 2rem 1rem;
    }
    .highlight {
        background: linear-gradient(120deg, #f8ffae 0%, #f8ffae 100%);
        padding: 2px 5px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)

# Header with animation
st.markdown("""
<div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 30px;">
    <h1 style="color: white; font-size: 3em; margin:0;">✨ Resumed</h1>
    <p style="color: white; font-size: 1.2em; opacity: 0.9;">Watch Your Resume Come to Life - Word by Word</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
        <h3 style="color: white; margin:0;">⚙️ Configuration</h3>
    </div>
    """, unsafe_allow_html=True)
    
    template_choice = st.selectbox(
        "Select Template Format:", 
        ["FAANG Template", "XYZ Format"],
        help="Choose the visual style for your resume"
    )
    
    st.markdown("---")
    
    st.markdown("""
    ### 🎯 Live Features
    - 👁️ **Real-time preview** - Watch your resume build
    - ✏️ **Interactive editing** - Click to edit any section
    - ⚡ **Instant updates** - Changes reflect immediately
    - 📊 **Progress tracking** - See generation in real-time
    
    ### How it works
    1. **Paste** your raw experience
    2. **Watch** as AI builds your resume line by line
    3. **Edit** any section interactively
    4. **Download** as Word or PDF
    """)
    
    st.markdown("---")
    
    # Add some stats if data exists
    if "resume_data" in st.session_state and st.session_state.resume_data:
        data = st.session_state.resume_data
        st.markdown("### 📊 Resume Stats")
        stats_col1, stats_col2 = st.columns(2)
        with stats_col1:
            exp_count = len(data.get('experience', []))
            st.metric("Experience", f"{exp_count} roles")
        with stats_col2:
            project_count = len(data.get('projects', []))
            st.metric("Projects", f"{project_count} projects")

# Initialize session state
if "resume_data" not in st.session_state:
    st.session_state.resume_data = None
if "generation_stage" not in st.session_state:
    st.session_state.generation_stage = 0
if "live_edit_mode" not in st.session_state:
    st.session_state.live_edit_mode = False

# Create tabs
tab1, tab2, tab3 = st.tabs(["📝 Input Your Details", "👁️ Live Preview", "✏️ Interactive Editor"])

with tab1:
    st.markdown("### 🚀 Drop Your Raw Experience Here")
    st.caption("💡 **Pro Tip:** Include your basic info, jobs, projects, and education. Watch as AI transforms it into a professional resume in real-time!")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        raw_text = st.text_area(
            "Experience & Projects:", 
            height=250, 
            placeholder="e.g., My name is John Doe. I worked at Google as a backend dev from 2021-2023. Built a scalable API that handled 1M+ requests...",
            key="raw_input"
        )
    
    with col2:
        st.markdown("""
        <div style="background: #e8f4fd; padding: 15px; border-radius: 10px;">
            <h4 style="margin:0">📋 Example</h4>
            <p style="font-size: 12px;">Include:<br>
            • Job titles & companies<br>
            • Dates<br>
            • Key achievements<br>
            • Projects<br>
            • Education<br>
            • Skills</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Progress indicators
    progress_bar = st.progress(0)
    status_text = st.empty()
    preview_placeholder = st.empty()
    
    if st.button("✨ Generate & Watch Resume Come to Life", use_container_width=True, type="primary"):
        if raw_text.strip():
            with st.spinner(""):
                result = extract_details_with_ai(raw_text, progress_bar, status_text, preview_placeholder)
                if result:
                    st.session_state.resume_data = result
                    st.session_state.live_edit_mode = True
                    
                    if result.get("name"):
                        save_name_to_sheets(result["name"])
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    preview_placeholder.empty()
                    
                    st.success("✅ Resume generated successfully! Go to the Live Preview tab to see the magic!")
                    
                    # Celebration animation
                    st.balloons()
        else:
            st.warning("⚠️ Please paste some text before generating.")

with tab2:
    if st.session_state.resume_data and st.session_state.live_edit_mode:
        data = st.session_state.resume_data
        
        # Export buttons
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        
        with col1:
            docx_file = generate_docx(data)
            st.download_button(
                label="📄 Download Word",
                data=docx_file,
                file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        
        with col2:
            # Generate PDF with appropriate template
            if template_choice == "FAANG Template":
                pdf_html = render_live_template(data, is_pdf=True, animation_stage=100)
            else:
                pdf_html = render_live_template(data, is_pdf=True, animation_stage=100)
            
            pdf_file = generate_pdf(pdf_html)
            if pdf_file:
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_file,
                    file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        
        with col4:
            # Animation speed control
            animation_speed = st.slider("Animation Speed", 0, 100, 100, key="anim_speed")
        
        st.markdown("---")
        
        # Live preview with animation
        st.subheader("🎬 Live Resume Preview - Watch It Build")
        
        # Create animation stages
        if st.button("▶️ Play Build Animation", use_container_width=True):
            anim_placeholder = st.empty()
            for stage in range(0, 101, 10):
                if template_choice == "FAANG Template":
                    preview_html = render_live_template(data, is_pdf=False, animation_stage=stage)
                else:
                    preview_html = render_live_template(data, is_pdf=False, animation_stage=stage)
                
                anim_placeholder.components.v1.html(preview_html, height=800, scrolling=True)
                time.sleep(0.1 * (100/animation_speed))
        
        # Final preview
        st.markdown("### 📄 Final Preview")
        if template_choice == "FAANG Template":
            preview_html = render_live_template(data, is_pdf=False, animation_stage=100)
        else:
            preview_html = render_live_template(data, is_pdf=False, animation_stage=100)
        
        st.components.v1.html(preview_html, height=800, scrolling=True)
            
    else:
        st.info("👈 Please generate your resume in the first tab to see the live preview!")

with tab3:
    if st.session_state.resume_data and st.session_state.live_edit_mode:
        st.markdown("### ✏️ Interactive Resume Editor")
        st.caption("Edit any section below and see changes reflected in real-time in the preview tab!")
        
        # Create interactive editor
        edited_data = create_interactive_editor(st.session_state.resume_data)
        
        # Update session state with edits
        st.session_state.resume_data = edited_data
        
        # Save button
        if st.button("💾 Save Changes", use_container_width=True):
            st.success("✅ Changes saved! Check the Live Preview tab to see updates.")
            st.balloons()
            
    else:
        st.info("👈 Please generate your resume first to use the interactive editor!")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>✨ Built with ❤️ using Streamlit and AI - Watch your resume come to life!</p>
</div>
""", unsafe_allow_html=True)
