# 📄 AI Resume Builder

An intelligent, AI-powered web application that transforms messy, unstructured text into perfectly formatted, professional resumes in seconds. 

Built with **Python** and **Streamlit**, this tool leverages the **OpenRouter API (GPT-4o-mini)** to act as an automated career coach—expanding brief job descriptions into impactful, industry-standard bullet points, inferring missing skills, and structuring the data into beautiful templates.

## ✨ Features
* **AI-Powered Generation:** Don't worry about formatting. Just brain-dump your experience, and the AI will organize it, fill in the blanks, and write professional descriptions.
* **Multiple Templates:** Choose from a clean, highly professional "FAANG" template or a modern, accented "XYZ" format.
* **Smart Parsing:** Automatically extracts and categorizes Personal Info, Summaries, Experience, Projects, Education, and Skills.
* **One-Click Export:** Download your final resume as a beautifully formatted Word Document (`.docx`) or a print-ready PDF (`.pdf`).

## 🛠️ Tech Stack
* **Frontend/UI:** [Streamlit](https://streamlit.io/)
* **AI/LLM:** [OpenRouter API](https://openrouter.ai/) (using GPT-4o-mini) / OpenAI Python SDK
* **Document Generation:** `python-docx` (for Word) and `xhtml2pdf` (for PDF)

## 🚀 Running it Locally

### Prerequisites
Make sure you have Python installed. You will also need an OpenRouter API key.

### 1. Clone the repository
```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
