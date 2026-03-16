import streamlit as st
import os
import json
import io
import time
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
# 2. Live Resume Builder with Word-by-Word Animation
# ==========================================
class LiveResumeBuilder:
    def __init__(self):
        self.resume_sections = {}
        self.current_section = None
        self.animation_speed = 0.02  # Seconds between words
        
    def stream_text(self, text, placeholder, speed=None):
        """Stream text word by word into a placeholder"""
        if speed is None:
            speed = self.animation_speed
            
        words = text.split()
        displayed_text = ""
        
        for word in words:
            displayed_text += word + " "
            placeholder.markdown(displayed_text + "▌")  # Add cursor effect
            time.sleep(speed)
        
        placeholder.markdown(displayed_text)  # Final text without cursor
        return displayed_text
    
    def build_resume_live(self, data, preview_container):
        """Build the complete resume section by section with animation"""
        
        # Create sections in the preview container
        with preview_container:
            # Header with name
            st.markdown("---")
            name_col1, name_col2, name_col3 = st.columns([1, 2, 1])
            with name_col2:
                name_placeholder = st.empty()
                if data.get('name'):
                    self.stream_text(f"# {data['name']}", name_placeholder, 0.03)
                time.sleep(0.5)
            
            # Contact info
            contact_placeholder = st.empty()
            if data.get('contact'):
                self.stream_text(f"*{data['contact']}*", contact_placeholder, 0.01)
            time.sleep(0.3)
            
            st.markdown("---")
            
            # Summary section
            if data.get('summary'):
                st.markdown("## 💼 Professional Summary")
                summary_placeholder = st.empty()
                self.stream_text(data['summary'], summary_placeholder)
                time.sleep(0.5)
            
            # Experience section
            if data.get('experience') and len(data['experience']) > 0:
                st.markdown("## 💻 Experience")
                for exp in data['experience']:
                    exp_header = f"### {exp.get('title', '')} at {exp.get('company', '')}"
                    st.markdown(exp_header)
                    
                    if exp.get('duration'):
                        st.markdown(f"*{exp['duration']}*")
                    
                    if exp.get('description'):
                        desc_placeholder = st.empty()
                        self.stream_text(exp['description'], desc_placeholder)
                        time.sleep(0.3)
                    
                    st.markdown("---")
            
            # Projects section
            if data.get('projects') and len(data['projects']) > 0:
                st.markdown("## 🚀 Projects")
                for proj in data['projects']:
                    proj_header = f"### {proj.get('name', '')}"
                    st.markdown(proj_header)
                    
                    if proj.get('tech_stack'):
                        st.markdown(f"*Tech: {proj['tech_stack']}*")
                    
                    if proj.get('description'):
                        proj_desc_placeholder = st.empty()
                        self.stream_text(proj['description'], proj_desc_placeholder)
                        time.sleep(0.3)
                    
                    st.markdown("---")
            
            # Education section
            if data.get('education') and len(data['education']) > 0:
                st.markdown("## 🎓 Education")
                for edu in data['education']:
                    edu_header = f"### {edu.get('university', '')}"
                    st.markdown(edu_header)
                    
                    if edu.get('degree'):
                        st.markdown(f"{edu['degree']}")
                    
                    if edu.get('year'):
                        st.markdown(f"*{edu['year']}*")
                    
                    st.markdown("---")
            
            # Skills section
            if data.get('skills'):
                st.markdown("## 🔧 Skills")
                skills_placeholder = st.empty()
                self.stream_text(data['skills'], skills_placeholder)
            
            # Final touch
            time.sleep(0.5)
            st.balloons()
            st.success("✅ Your resume has been built successfully!")

# ==========================================
# 3. AI Processing with Live Feedback
# ==========================================
def extract_details_with_ai(raw_text, progress_callback=None):
    """Extract details with progress updates"""
    
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
    
    if progress_callback:
        progress_callback("Analyzing your experience...")
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_text}
            ],
            response_format={"type": "json_object"}
        )
        
        if progress_callback:
            progress_callback("Formatting your resume...")
            
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

    # Helper function for left/right aligned headers
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
    """Converts HTML to PDF"""
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html_content.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

def render_faang_template(data, is_pdf=False):
    """HTML template for resume"""
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

    if data.get('summary'):
        html += f"""
        <div class="section-title">Professional Summary</div>
        <p style="margin-top: 0; font-size: 11px;">{data['summary']}</p>
        """

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

# Custom CSS for better animations
st.markdown("""
<style>
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .stProgress > div > div > div > div {
        background-color: #00ff00;
    }
    .cursor {
        animation: pulse 1s infinite;
    }
</style>
""", unsafe_allow_html=True)

st.title("📄 Resumed - Watch Your Resume Build in Real-Time")
st.info("🎬 *Watch as your resume is built word by word in front of your eyes!*")

with st.sidebar:
    st.header("⚙️ Configuration")
    template_choice = st.selectbox("Select Template Format:", ["FAANG Template", "XYZ Format"])
    
    st.markdown("---")
    st.markdown("### Animation Settings")
    animation_speed = st.slider("Animation Speed", 0.01, 0.1, 0.02, 0.01, 
                                format="%.2f sec/word")
    
    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("1. **Paste** your raw experience")
    st.markdown("2. **Watch** as AI builds your resume live")
    st.markdown("3. **Download** the final formatted version")

if "resume_data" not in st.session_state:
    st.session_state.resume_data = None
if "builder" not in st.session_state:
    st.session_state.builder = LiveResumeBuilder()

tab1, tab2, tab3 = st.tabs(["📝 1. Enter Your Details", "🎬 2. Watch Live Build", "📄 3. Export & Download"])

with tab1:
    st.markdown("### Drop your raw background here")
    st.caption("💡 **Pro Tip:** Include your basic info, jobs, projects, and education. Watch the magic happen in the next tab!")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        raw_text = st.text_area("Experience & Projects:", height=250, 
                               placeholder="e.g., My name is John Doe. I worked at Google as a backend dev from 2021-2023. Built a scalable API... ",
                               key="raw_input")

    with col2:
        st.markdown("### Quick Examples")
        if st.button("📋 Load Sample"):
            sample = """My name is Sarah Johnson. I'm a software engineer with 5 years experience at Microsoft where I worked on Azure cloud services from 2019-2024. Led a team of 4 developers in building a monitoring system. Before that, I was at a startup called TechFlow from 2017-2019 where I built mobile apps. I have a CS degree from Stanford University (2017). Skills include Python, JavaScript, AWS, and team leadership."""
            st.session_state.raw_input = sample
            st.rerun()

    if st.button("✨ Generate & Watch Resume Build Live", use_container_width=True, type="primary"):
        if raw_text.strip():
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message):
                status_text.info(message)
                progress_bar.progress(min(progress_bar.progress + 0.25, 1.0))
            
            with st.spinner("AI is analyzing your experience..."):
                result = extract_details_with_ai(raw_text, update_progress)
                
                if result:
                    st.session_state.resume_data = result
                    st.session_state.builder.animation_speed = animation_speed
                    
                    if result.get("name"):
                        save_name_to_sheets(result["name"])
                    
                    progress_bar.progress(1.0)
                    status_text.success("✅ Resume data prepared! Go to the 'Watch Live Build' tab to see it being created!")
                    time.sleep(1)
                    status_text.empty()
                    progress_bar.empty()
        else:
            st.warning("Please paste some text before generating.")

with tab2:
    if st.session_state.resume_data:
        st.markdown("## 🎬 Live Resume Building in Progress")
        st.caption("Watch as your resume is constructed word by word...")
        
        # Controls for the animation
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("▶️ Start Building", use_container_width=True):
                st.session_state.start_build = True
        
        st.markdown("---")
        
        # Live preview container
        preview_container = st.container()
        
        # Trigger the live build
        if st.session_state.get('start_build', False):
            with st.spinner("Building your resume..."):
                st.session_state.builder.build_resume_live(
                    st.session_state.resume_data, 
                    preview_container
                )
            st.session_state.start_build = False
        else:
            with preview_container:
                st.info("👆 Click 'Start Building' to watch your resume being created in real-time!")
                
                # Show a preview of what will be built
                with st.expander("Preview of sections to be built"):
                    data = st.session_state.resume_data
                    st.json({
                        "Name": data.get('name', ''),
                        "Sections": {
                            "Summary": "✓" if data.get('summary') else "✗",
                            "Experience": f"{len(data.get('experience', []))} entries",
                            "Projects": f"{len(data.get('projects', []))} entries",
                            "Education": f"{len(data.get('education', []))} entries",
                            "Skills": "✓" if data.get('skills') else "✗"
                        }
                    })
    else:
        st.info("👈 Please enter your details in the first tab to generate your resume.")

with tab3:
    if st.session_state.resume_data:
        data = st.session_state.resume_data
        
        st.markdown("## 📄 Export Your Resume")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        # Generate the appropriate template
        if template_choice == "FAANG Template":
            pdf_html = render_faang_template(data, is_pdf=True)
        else:
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
            pdf_file = generate_pdf(pdf_html)
            if pdf_file:
                st.download_button(
                    label="📥 Download PDF (.pdf)",
                    data=pdf_file,
                    file_name=f"{data.get('name', 'Resume').replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        with col3:
            # Option to rewatch the build
            if st.button("🎬 Rewatch Build Process", use_container_width=True):
                st.session_state.start_build = True
                st.switch_page(tab2)
                
        st.markdown("---")
        
        st.subheader("Final Resume Preview")
        if template_choice == "FAANG Template":
            preview_html = render_faang_template(data, is_pdf=False)
        else:
            preview_html = render_xyz_template(data, is_pdf=False)
            
        st.components.v1.html(preview_html, height=800, scrolling=True)
            
    else:
        st.info("👈 Generate your resume first to see export options here.")
