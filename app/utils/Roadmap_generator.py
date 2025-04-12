import os
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
import pprint
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
groq_api_key = os.getenv('GROQ_API_KEY')


def generate_roadmap(groq_api_key, resume_pdf_path):
    if groq_api_key:
        llm = ChatGroq(
            model="llama3-70b-8192",
            api_key=groq_api_key
        )
        pdfloader = PyPDFLoader(resume_pdf_path)
        resume_data = pdfloader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=8000,
            chunk_overlap=200
        )
        resume_chunks = text_splitter.split_documents(resume_data)
        combined_resume_content = " ".join([chunk.page_content for chunk in resume_chunks])

        career_analysis_prompt = ChatPromptTemplate.from_template(
            """
            You are a professional career advisor and technology expert. 
            Analyze the following resume and extract key information:

            Resume:
            {resume_content}

            Provide a structured JSON response with the following information:
            1. Current skills and technologies identified in the resume
            2. Professional level assessment (e.g., entry, mid, senior)
            3. Primary technical domains (e.g., web development, data science, etc.)

            Format your response ONLY as a valid JSON object.
            """
        )
        career_analysis_chain = (
                {"resume_content": RunnablePassthrough()}
                | career_analysis_prompt
                | llm
                | StrOutputParser()
        )
        analysis_result = career_analysis_chain.invoke(combined_resume_content)

        try:
            analysis_data = json.loads(analysis_result)
        except json.JSONDecodeError:

            start_idx = analysis_result.find('{')
            end_idx = analysis_result.rfind('}') + 1

            if start_idx != -1 and end_idx != 0:
                json_str = analysis_result[start_idx:end_idx]
                try:
                    analysis_data = json.loads(json_str)
                except:

                    analysis_data = {
                        "current_skills": ["Unable to parse skills"],
                        "professional_level": "Unknown",
                        "technical_domains": ["Unable to parse domains"]
                    }
            else:

                analysis_data = {
                    "current_skills": ["Unable to parse skills"],
                    "professional_level": "Unknown",
                    "technical_domains": ["Unable to parse domains"]
                }
            if "current_skills" not in analysis_data:

                if "skills" in analysis_data:
                    analysis_data["current_skills"] = analysis_data["skills"]
                else:
                    analysis_data["current_skills"] = ["Skills not identified"]

        roadmap_prompt = ChatPromptTemplate.from_template(
            """
            You are a professional career and technology advisor with deep expertise in software development, 
            data science, and technology career paths. Your task is to create a detailed, personalized
            learning roadmap for a professional with the following profile:

            Profile:
            {profile}

            Create a comprehensive, personalized roadmap that includes:

            1. IMMEDIATE NEXT SKILLS (3-5): Specific skills and technologies they should learn next based on 
               industry standards and career progression. Explain WHY each skill is important for their growth.

            2. LEARNING PATH: A structured 6-month learning path with specific resources, milestones, and 
               time estimates. Consider modern industry standards and practical applications.

            3. CAREER DIRECTION: Suggest 2-3 potential specialized career paths they could pursue given their 
               current foundation, and what each path would require.

            4. INDUSTRY INSIGHTS: Share 2-3 key industry insights about how their domain is evolving and 
               what skills are becoming more valuable.

            Format your response as a detailed roadmap with clear sections, practical advice, and 
            specific next steps. Include specific learning resources when appropriate.
            """
        )

        roadmap_chain = (
                {"profile": lambda _: pprint.pformat(analysis_data)}
                | roadmap_prompt
                | llm
                | StrOutputParser()
        )
        roadmap_result = roadmap_chain.invoke({})

        final_result = {
            "profile_analysis": analysis_data,
            "personalized_roadmap": roadmap_result
        }
        return final_result

def get_resume_path():
    base_dir = Path(__file__).parent.parent
    filepath = base_dir/"media"/"Resume"/"DemoResume.pdf"
    return filepath


if __name__ == "__main__":
    pdf_path = get_resume_path()

    result = generate_roadmap(groq_api_key=groq_api_key, resume_pdf_path=pdf_path)

    if result:
        resume_analysis = result["profile_analysis"]
        roadmap = result["personalized_roadmap"]


        print("Raw analysis:", resume_analysis)


        skills = resume_analysis.get("current_skills", ["No skills identified"])
        print("Skills identified:", skills)

        print("\nPersonalized Roadmap:")
        print(roadmap)
