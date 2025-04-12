import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


class ResumeBuilder:

    def __init__(self,
                 google_api_key: str,
                 template_path: Optional[str] = None,
                 model_name: str = "gemini-1.5-pro"):

        self.google_api_key = google_api_key
        self.model_name = model_name
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.google_api_key,
            temperature=0.1,
            max_output_tokens=100000
        )

        if template_path:
            self.template_path = template_path
        else:

            temp_dir = tempfile.mkdtemp()
            self.template_path = os.path.join(temp_dir, "default_template.tex")
            with open(self.template_path, "w") as f:
                f.write(self._get_default_template())

        self.output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_default_template(self) -> str:

        return r"""
\documentclass[a4paper,11pt]{article}

% Package imports
\usepackage{latexsym}
\usepackage{xcolor}
\usepackage{float}
\usepackage{ragged2e}
\usepackage[empty]{fullpage}
\usepackage{wrapfig}
\usepackage{tabularx}
\usepackage{titlesec}
\usepackage{geometry}
\usepackage{marvosym}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage{multicol}
\usepackage{graphicx}
\usepackage{cfr-lm}
\usepackage[T1]{fontenc}
\usepackage{fontawesome5}
\usepackage[hidelinks]{hyperref}
\usepackage{microtype}
\usepackage{tabularx} % Required for tables that stretch to page width
\usepackage{array} % Required for vertical centering in tables

% Color definitions
\definecolor{darkblue}{RGB}{0,0,139}

% Page layout
\geometry{left=1.4cm, top=0.8cm, right=1.2cm, bottom=1cm}
\setlength{\multicolsep}{0pt} 
\pagestyle{fancy}
\fancyhf{} % clear all header and footer fields
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\setlength{\footskip}{4.08pt}

% Hyperlink setup
\hypersetup{
    colorlinks=true,
    linkcolor=darkblue,
    filecolor=darkblue,
    urlcolor=darkblue,
}

% Custom box settings
\usepackage[most]{tcolorbox}
\tcbset{
    frame code={},
    center title,
    left=0pt,
    right=0pt,
    top=0pt,
    bottom=0pt,
    colback=gray!20,
    colframe=white,
    width=\dimexpr\textwidth\relax,
    enlarge left by=-2mm,
    boxsep=4pt,
    arc=0pt,outer arc=0pt,
}

% URL style
\urlstyle{same}

% Text alignment
\raggedright
\setlength{\tabcolsep}{0in}

% Section formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{-7pt}]

% Custom commands
\newcommand{\resumeItem}[2]{
  \item{
    \textbf{#1}{\hspace{0.5mm}#2 \vspace{-0.5mm}}
  }
}

\newcommand{\resumePOR}[3]{
\vspace{0.5mm}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
        \textbf{#1}\hspace{0.3mm}#2 & \textit{\small{#3}} 
    \end{tabular*}
    \vspace{-2mm}
}

\newcommand{\resumeSubheading}[4]{
\vspace{0.5mm}\item
    \begin{tabular*}{0.98\textwidth}[t]{l@{\extracolsep{\fill}}r}
        \textbf{#1} & \textit{\footnotesize{#4}} \\
        \textit{\footnotesize{#3}} &  \footnotesize{#2}\\
    \end{tabular*}
    \vspace{-2.4mm}
}

\newcommand{\resumeProject}[4]{
\vspace{0.5mm}\item
    \begin{tabular*}{0.98\textwidth}[t]{l@{\extracolsep{\fill}}r}
        \textbf{#1} & \textit{\footnotesize{#3}} \\
        \footnotesize{\textit{#2}} & \footnotesize{#4}
    \end{tabular*}
    \vspace{-2.4mm}
}

\newcommand{\resumeSubItem}[2]{\resumeItem{#1}{#2}\vspace{-4pt}}

\renewcommand{\labelitemi}{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand{\labelitemii}{$\vcenter{\hbox{\tiny$\circ$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=*,labelsep=1mm]}
\newcommand{\resumeHeadingSkillStart}{\begin{itemize}[leftmargin=*,itemsep=1.7mm, rightmargin=2ex]}
\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=*,labelsep=1mm,itemsep=0.5mm]}

\newcommand{\resumeSubHeadingListEnd}{\end{itemize}\vspace{2mm}}
\newcommand{\resumeHeadingSkillEnd}{\end{itemize}\vspace{-2mm}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-2mm}}
\newcommand{\cvsection}[1]{%
\vspace{2mm}
\begin{tcolorbox}
    \textbf{\large #1}
\end{tcolorbox}
    \vspace{-4mm}
}

\newcolumntype{L}{>{\raggedright\arraybackslash}X}%
\newcolumntype{R}{>{\raggedleft\arraybackslash}X}%
\newcolumntype{C}{>{\centering\arraybackslash}X}%

% Commands for icon sizing and positioning
\newcommand{\socialicon}[1]{\raisebox{-0.05em}{\resizebox{!}{1em}{#1}}}
\newcommand{\ieeeicon}[1]{\raisebox{-0.3em}{\resizebox{!}{1.3em}{#1}}}

% Define personal information
\newcommand{\name}{NAME_PLACEHOLDER} % Your Name
\newcommand{\course}{COURSE_PLACEHOLDER} % Your Course
\newcommand{\roll}{ROLL_PLACEHOLDER} % Your Roll No.
\newcommand{\phone}{PHONE_PLACEHOLDER} % Your Phone Number
\newcommand{\emaila}{EMAIL_PLACEHOLDER} % Email 1
\newcommand{\emailb}{EMAIL_PLACEHOLDER} % Email 2
\newcommand{\github}{GITHUB_PLACEHOLDER} % Github
\newcommand{\website}{WEBSITE_PLACEHOLDER} % Website
\newcommand{\linkedin}{LINKEDIN_PLACEHOLDER} % LinkedIn

\begin{document}
\fontfamily{cmr}\selectfont

%----------HEADING-----------------
\parbox{2.35cm}{%
\includegraphics[width=2cm,clip]{logo.png}
}
\parbox{\dimexpr\linewidth-2.8cm\relax}{
\begin{tabularx}{\linewidth}{L r}
  \textbf{\LARGE \name} & +91-\phone \\
  \course & \href{mailto:\emaila}{\emaila} \\
  DEPARTMENT_PLACEHOLDER & \href{https://www.linkedin.com/in/\linkedin}{linkedin.com/in/\linkedin} \\
  INSTITUTION_PLACEHOLDER & \href{https://github.com/\github}{github.com/\github} \\
\end{tabularx}
}
\vspace{-2mm}

CONTENT_PLACEHOLDER

\end{document}
"""

    def extract_content_from_pdf(self, resume_pdf_path: str) -> List[Document]:

        try:
            loader = PyPDFLoader(resume_pdf_path)
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=200
            )

            return text_splitter.split_documents(documents)
        except Exception as e:
            print(f"Error extracting content from PDF: {e}")
            return []

    def generate_resume_latex(self,
                              user_info: Dict[str, str],
                              resume_chunks: List[Document],
                              sections: List[str]) -> str:

        with open(self.template_path, "r") as f:
            template_content = f.read()

        context = "\n\n".join([doc.page_content for doc in resume_chunks])

        content_template = """
        You are a professional resume writer tasked with creating a LaTeX resume.

        I will provide you with:
        1. Context from an old resume: {context}
        2. A list of sections to include: {sections}

        Please generate the LaTeX code for the content of a resume with the requested sections. 
        The content should be professional, concise, and formatted correctly for a LaTeX document.

        Please follow these guidelines:
        - Maintain the same structure and style as the original resume where appropriate
        - Use bullet points for listing achievements, responsibilities, and skills
        - Ensure all dates are formatted consistently
        - Keep descriptions concise and achievement-focused
        - Use action verbs at the beginning of bullet points
        - Only include the sections requested

        The LaTeX should include all sections between the header and the end of the document but NOT the entire LaTeX document (no preamble).
        Only generate the content that would replace "CONTENT_PLACEHOLDER" in the template.

        Here are the sections I need: {sections}
        """

        content_prompt = PromptTemplate(
            input_variables=["context", "sections"],
            template=content_template
        )

        content_chain = LLMChain(
            llm=self.llm,
            prompt=content_prompt
        )

        try:
            sections_str = ", ".join(sections)
            content_result = content_chain.run(context=context, sections=sections_str)

            latex_code = template_content
            for key, value in user_info.items():
                placeholder = f"{key.upper()}_PLACEHOLDER"
                latex_code = latex_code.replace(placeholder, value)

            latex_code = latex_code.replace("CONTENT_PLACEHOLDER", content_result)

            return latex_code
        except Exception as e:
            print(f"Error generating resume content: {e}")
            return ""

    def compile_latex_to_pdf(self, latex_code: str, output_filename: str) -> str:

        try:

            with tempfile.TemporaryDirectory() as temp_dir:

                tex_file_path = os.path.join(temp_dir, "resume.tex")
                with open(tex_file_path, "w") as f:
                    f.write(latex_code)

                # Copy logo.png to temp directory if it exists, or create a placeholder
                logo_path = os.path.join(os.path.dirname(self.template_path), "logo.png")
                temp_logo_path = os.path.join(temp_dir, "logo.png")

                if os.path.exists(logo_path):
                    import shutil
                    shutil.copy2(logo_path, temp_logo_path)
                else:

                    try:
                        from PIL import Image, ImageDraw
                        img = Image.new('RGB', (200, 200), color=(255, 255, 255))
                        d = ImageDraw.Draw(img)
                        d.rectangle([(20, 20), (180, 180)], outline=(0, 0, 0))
                        d.text((70, 90), "LOGO", fill=(0, 0, 0))
                        img.save(temp_logo_path)
                    except ImportError:
                        print("PIL not installed. Using a blank logo.")
                        with open(temp_logo_path, "wb") as f:
                            f.write(
                                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d\x00\x00\x00d\x08\x02\x00\x00\x00\xff\x80\x02\x03\x00\x00\x00\x06bKGD\x00\xff\x00\xff\x00\xff\xa0\xbd\xa7\x93\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x07tIME\x07\xe5\n\x1a\x16\x08\x08\xd8\x03\xc5\x05\x00\x00\x00\x19tEXtComment\x00Created with GIMPW\x81\x0e\x17\x00\x00\x00\x0cIDAT\x18\xd3c\x18\x05\xa3`\x14\x8c\x82\x01\x06\x00\x04P\x00\x01\xf4\xaf\xba\xd5\x00\x00\x00\x00IEND\xaeB`\x82')

                os.chdir(temp_dir)
                process = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "resume.tex"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if process.returncode != 0:
                    print(f"LaTeX compilation error: {process.stderr}")
                    return ""

                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "resume.tex"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                pdf_path = os.path.join(temp_dir, "resume.pdf")
                output_path = os.path.join(self.output_dir, f"{output_filename}.pdf")

                if os.path.exists(pdf_path):
                    import shutil
                    shutil.copy2(pdf_path, output_path)
                    return output_path
                else:
                    print("PDF file was not generated")
                    return ""
        except Exception as e:
            print(f"Error compiling LaTeX to PDF: {e}")
            return ""

    def build_resume(self,
                     resume_pdf_path: str,
                     user_info: Dict[str, str],
                     sections: List[str] = None,
                     output_filename: str = "generated_resume") -> str:
        if sections is None:
            sections = [
                "Education",
                "Experience",
                "Projects",
                "Skills",
                "Certifications",
                "Achievements",
                "Positions of Responsibility"
            ]

        resume_chunks = self.extract_content_from_pdf(resume_pdf_path)

        if not resume_chunks:
            print("Failed to extract content from the PDF")
            return ""

        latex_code = self.generate_resume_latex(user_info, resume_chunks, sections)

        if not latex_code:
            print("Failed to generate LaTeX code")
            return ""

        pdf_path = self.compile_latex_to_pdf(latex_code, output_filename)

        if pdf_path:
            print(f"Resume successfully generated at: {pdf_path}")
            return pdf_path
        else:
            print("Failed to compile LaTeX to PDF")
            return ""


# Example usage
if __name__ == "__main__":
    GOOGLE_API_KEY = "your_google_api_key_here"

    resume_builder = ResumeBuilder(google_api_key=GOOGLE_API_KEY)
    user_info = {
        "name": "John",
        "course": "Bachelor of Technology",
        "roll": "CSE",
        "phone": "9876543210",
        "emaila": "john@example.com",
        "department": "Computer Science Engineering",
        "institution": "National Institute of Technology, Patna",
        "github": "johndoe",
        "linkedin": "john-doe-123456"
    }

    pdf_path = resume_builder.build_resume(
        resume_pdf_path="path_to_your_old_resume.pdf",
        user_info=user_info,
        sections=["Education", "Experience", "Projects", "Skills", "Certifications"],
        output_filename="john_doe_resume"
    )

    print(f"Resume generated at: {pdf_path}")
