import os
from PyPDF2 import PdfReader
import spacy
import re
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv


class ResumeScorer:
    def __init__(self, groq_api_key, resume_pdf_path=None):

        self.nlp = spacy.load("en_core_web_sm")
        self.resume_pdf_path = resume_pdf_path
        self.api_key = groq_api_key
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=self.api_key
        )

    def extract_resume_text(self, resume_pdf_path=None):

        pdf_path = resume_pdf_path or self.resume_pdf_path

        if not pdf_path:
            raise ValueError("No PDF path provided. Either set it during initialization or provide it as a parameter.")

        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text += page.extract_text()
        except Exception as e:
            print(f"Error extracting from PDF: {e}")
        return text

    def extract_sections(self, text):

        section_patterns = {
            "education": r"(?i)education|academic|degree|university|college|school",
            "experience": r"(?i)experience|work|employment|job|career|professional",
            "skills": r"(?i)skills|expertise|proficiencies|competencies|technical|tools",
            "projects": r"(?i)projects|portfolio|works|implementations",
            "certifications": r"(?i)certifications|certificates|licenses|credentials",
            "achievements": r"(?i)achievements|awards|honors|accomplishments",
            "summary": r"(?i)summary|profile|objective|about me|overview"
        }

        sections = {}
        lines = text.split('\n')
        current_section = "other"
        sections[current_section] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            for section_name, pattern in section_patterns.items():
                if re.search(pattern, line) and len(line) < 50:
                    current_section = section_name
                    if current_section not in sections:
                        sections[current_section] = []
                    break
            else:
                sections[current_section].append(line)

        for section in sections:
            sections[section] = "\n".join(sections[section])
        return sections

    def analyze_experience_quality(self, experience_text):

        score = 0

        action_verbs = [
            "achieved", "improved", "trained", "managed", "created", "increased",
            "reduced", "negotiated", "directed", "launched", "developed", "designed",
            "implemented", "led", "organized", "produced", "supervised", "built",
            "coordinated", "delivered", "established", "executed", "generated"
        ]

        verb_count = sum(1 for verb in action_verbs if re.search(r'\b' + verb + r'\b', experience_text.lower()))
        quantifiable = len(re.findall(r'\d+%|\$\d+|\d+ years|\d+ people|\d+ team', experience_text))
        doc = self.nlp(experience_text)
        tech_terms = len([ent for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "GPE"]])

        score = min(25, verb_count * 2 + quantifiable * 3 + tech_terms)
        return score

    def get_llm_feedback(self, resume_text, sections, token_efficient=True):

        try:
            if token_efficient:
                summary = ""
                for section_name in ["summary", "experience", "skills", "education"]:
                    if section_name in sections and sections[section_name]:
                        content = sections[section_name][:500] + "..." if len(sections[section_name]) > 500 else \
                            sections[section_name]
                        summary += f"\n--- {section_name.upper()} ---\n{content}\n"

                prompt_template = """
                You are a resume expert. Analyze this resume for relevant strengths and weaknesses:

                {resume_summary}

                Return a JSON with these fields only:
                1. strengths (list 3 key strengths, 1-2 words each)
                2. weaknesses (list 2 key areas needing improvement, 1-2 words each)
                3. overall_score (number between 0-30)
                """

                chain = LLMChain(
                    llm=self.llm,
                    prompt=PromptTemplate(
                        input_variables=["resume_summary"],
                        template=prompt_template
                    )
                )

                response = chain.run(resume_summary=summary)

            else:
                prompt_template = """
                You are a resume expert. Analyze this full resume:

                {resume_text}

                Return a JSON with these fields:
                1. strengths (list up to 5)
                2. weaknesses (list up to 3)
                3. improvement_suggestions (list up to 3)
                4. overall_score (number between 0-30)
                5. keyword_relevance (on a scale of 1-10)
                """

                chain = LLMChain(
                    llm=self.llm,
                    prompt=PromptTemplate(
                        input_variables=["resume_text"],
                        template=prompt_template
                    )
                )

                response = chain.run(resume_text=resume_text)

            import json
            try:
                result = json.loads(response)
                llm_score = result.get("overall_score", 15)
            except:
                llm_score = 15

            return llm_score

        except Exception as e:
            print(f"Error getting LLM feedback: {e}")
            return 15

    def score_resume(self, resume_text=None):

        if resume_text is None:
            resume_text = self.extract_resume_text()

        sections = self.extract_sections(resume_text)

        section_score = 0
        content_score = 0
        format_score = 0
        llm_score = 0

        key_sections = {"summary": 3, "education": 4, "experience": 6, "skills": 4, "projects": 2, "certifications": 1}
        for section, weight in key_sections.items():
            if section in sections and len(sections[section]) > 20:
                section_score += weight

        if "experience" in sections:
            content_score += self.analyze_experience_quality(sections["experience"])

        if "skills" in sections:
            skills_text = sections["skills"].lower()
            tech_skills = ["python", "java", "javascript", "sql", "aws", "cloud", "docker",
                           "kubernetes", "react", "node", "machine learning", "data", "api"]
            soft_skills = ["leadership", "communication", "teamwork", "problem solving",
                           "analytical", "project management", "agile"]

            tech_count = sum(1 for skill in tech_skills if skill in skills_text)
            soft_count = sum(1 for skill in soft_skills if skill in skills_text)

            content_score += min(15, tech_count * 1.5 + soft_count)

        word_count = len(resume_text.split())
        if 400 <= word_count <= 1000:
            format_score += 5
        elif 300 <= word_count < 400 or 1000 < word_count <= 1200:
            format_score += 3

        bullet_patterns = [r'•', r'\\-', r'\*', r'\d+\.\s']
        has_bullets = any(re.search(pattern, resume_text) for pattern in bullet_patterns)
        if has_bullets:
            format_score += 5

        llm_score = self.get_llm_feedback(resume_text, sections, token_efficient=True)

        final_score = min(100, section_score + content_score + format_score + llm_score)

        feedback = {
            "total_score": final_score,
            "section_score": section_score,
            "content_score": content_score,
            "format_score": format_score,
            "llm_score": llm_score,
            "sections_found": list(sections.keys()),
            "word_count": word_count
        }

        return feedback

    def run_scorer(self, pdf_path=None):

        if pdf_path:
            self.resume_pdf_path = pdf_path

        resume_text = self.extract_resume_text()

        results = self.score_resume(resume_text)

        print(f"Resume Score: {results['total_score']}/100")
        print(f"Sections Score: {results['section_score']}/20")
        print(f"Content Score: {results['content_score']}/40")
        print(f"Format Score: {results['format_score']}/10")
        print(f"LLM Analysis Score: {results['llm_score']}/30")
        print(f"Sections found: {', '.join(results['sections_found'])}")
        print(f"Word count: {results['word_count']}")

        return results
