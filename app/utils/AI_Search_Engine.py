from pymongo import MongoClient
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
import os
import PyPDF2
import io
import re
from typing import List, Dict, Any, Tuple, Optional
import logging
from dotenv import load_dotenv

load_dotenv()
groq_api_key = os.getenv('GROQ_API_KEY')
mongodb_uri = os.getenv('MONGO_URI')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, mongodb_uri: str, db_name: str = "users", collection_name: str = "users",
                 chroma_persist_directory: str = "./chroma_db", groq_api_key: str = None):

        self.mongo_client = MongoClient(mongodb_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        self.chroma_persist_directory = chroma_persist_directory

        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        self.vector_store = None
        self._initialize_vector_store()

        self.llm = None
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
            self.llm = ChatGroq(temperature=0.2, model_name="llama3-70b-8192")
        else:
            logger.warning("No Groq API key provided. AI search features will be unavailable.")

    def _initialize_vector_store(self):
        try:

            self.vector_store = Chroma(
                persist_directory=self.chroma_persist_directory,
                embedding_function=self.embeddings
            )
            logger.info(f"Loaded existing vector store with {self.vector_store._collection.count()} documents")
        except Exception as e:
            logger.info(f"Creating new vector store: {e}")
            self.vector_store = Chroma(
                persist_directory=self.chroma_persist_directory,
                embedding_function=self.embeddings
            )

    def _extract_text_from_pdf(self, pdf_binary: bytes) -> str:

        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_binary))
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def _extract_text_from_pdf_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()
                return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF file: {e}")
            return ""
    def index_user(self, user_id: str) -> bool:

        try:

            user = self.collection.find_one({"_id": user_id})
            if not user:
                logger.warning(f"User {user_id} not found in MongoDB")
                return False


            resume_text = ""
            if 'resume_pdf' in user and user['resume_pdf']:
                resume_text = self._extract_text_from_pdf(user['resume_pdf'])
            elif 'resume_path' in user and user['resume_path']:
                resume_text = self._extract_text_from_pdf_file(user['resume_path'])
            profile_text = f"""
                    Name: {user.get('name', 'N/A')}
                    Department: {user.get('department', 'N/A')}
                    LinkedIn: {user.get('linkedin', 'N/A')}
                    GitHub: {user.get('github', 'N/A')}
                    About: {user.get('about_yourself', 'N/A')}
                    Resume Score: {user.get('resume_score', 0)}

                    Resume Text:
                    {resume_text}
                    """

            # Create document for ChromaDB
            document = Document(
                page_content=profile_text,
                metadata={
                    "user_id": str(user_id),
                    "name": user.get('name', 'N/A'),
                    "resume_score": user.get('resume_score', 0),
                    "department": user.get('department', 'N/A')
                }
            )

            # Add to vector store
            self.vector_store.add_documents([document])
            self.vector_store.persist()

            logger.info(f"Successfully indexed user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error indexing user {user_id}: {e}")
            return False

    def index_all_users(self) -> int:

        success_count = 0
        all_users = self.collection.find({})

        for user in all_users:
            if self.index_user(user["_id"]):
                success_count += 1

        logger.info(f"Indexed {success_count} users out of {self.collection.count_documents({})}")
        return success_count

    def basic_search(self, job_description: str, limit: int = 10, min_score: float = 0.0) -> List[Dict[str, Any]]:

        try:

            results = self.vector_store.similarity_search_with_score(job_description, k=limit)

            candidates = []
            for doc, score in results:

                normalized_score = 1 - score

                if normalized_score >= min_score:
                    user_id = doc.metadata.get("user_id")

                    user = self.collection.find_one({"_id": user_id})

                    if user:

                        candidate = {
                            "user_id": user_id,
                            "name": user.get("name", "N/A"),
                            "department": user.get("department", "N/A"),
                            "resume_score": user.get("resume_score", 0),
                            "match_score": round(normalized_score * 100, 2),
                            "linkedin": user.get("linkedin_link", ""),
                            "github": user.get("github_link", "")
                        }
                        candidates.append(candidate)


            candidates.sort(key=lambda x: (x["match_score"], x["resume_score"]), reverse=True)
            return candidates

        except Exception as e:
            logger.error(f"Error in basic search: {e}")
            return []

    def ai_search(self, job_description: str, limit: int = 5) -> List[Dict[str, Any]]:

        if not self.llm:
            logger.error("AI search unavailable: Groq LLM not initialized")
            return []

        try:

            candidates = self.basic_search(job_description,
                                           limit=limit * 2)

            enhanced_candidates = []

            for candidate in candidates[:limit]:
                user_id = candidate["user_id"]
                user = self.collection.find_one({"_id": user_id})

                if not user:
                    continue


                resume_text = ""
                if 'resume_pdf' in user and user['resume_pdf']:
                    resume_text = self._extract_text_from_pdf(user['resume_pdf'])


                profile = f"""
                Candidate Name: {user.get('name', 'N/A')}
                Department: {user.get('department', 'N/A')}
                About: {user.get('about', 'N/A')}
                LinkedIn: {user.get('linkedin_link', 'N/A')}
                GitHub: {user.get('github_link', 'N/A')}

                Resume Highlights:
                {resume_text[:2000]}  
                """


                prompt_template = PromptTemplate(
                    template="""
                    You are an expert recruiter AI. Analyze the candidate's profile against the job requirements.

                    Job Description:
                    {job_description}

                    Candidate Profile:
                    {candidate_profile}

                    Provide a detailed analysis with the following:
                    1. Match Score (0-100): Numerical assessment of how well the candidate fits the role
                    2. Key Strengths: List 2-3 top strengths relevant to this position
                    3. Potential Gaps: Identify 1-2 areas where the candidate might need development
                    4. Overall Recommendation: 1-2 sentence summary of fit for the position

                    Format your response as a JSON object with the following fields:
                    "match_score", "key_strengths", "potential_gaps", "recommendation"
                    """,
                    input_variables=["job_description", "candidate_profile"]
                )


                chain = prompt_template | self.llm

                response = chain.invoke({
                    "job_description": job_description,
                    "candidate_profile": profile
                })


                try:

                    json_match = re.search(r'({.*})', response.content, re.DOTALL)
                    if json_match:
                        import json
                        analysis = json.loads(json_match.group(1))
                    else:
                        analysis = {
                            "match_score": candidate["match_score"],
                            "key_strengths": ["Could not extract"],
                            "potential_gaps": ["Could not extract"],
                            "recommendation": "Could not generate AI recommendation."
                        }
                except Exception as e:
                    logger.error(f"Error parsing AI response: {e}")
                    analysis = {
                        "match_score": candidate["match_score"],
                        "key_strengths": ["Error in analysis"],
                        "potential_gaps": ["Error in analysis"],
                        "recommendation": "Error generating AI recommendation."
                    }


                enhanced_candidate = {
                    **candidate,
                    "ai_match_score": analysis.get("match_score", candidate["match_score"]),
                    "key_strengths": analysis.get("key_strengths", []),
                    "potential_gaps": analysis.get("potential_gaps", []),
                    "recommendation": analysis.get("recommendation", "No recommendation available.")
                }

                enhanced_candidates.append(enhanced_candidate)

            enhanced_candidates.sort(key=lambda x: x["ai_match_score"], reverse=True)
            return enhanced_candidates

        except Exception as e:
            logger.error(f"Error in AI search: {e}")
            return []

    def smart_search(self, job_description: str, limit: int = 5, use_ai: bool = True) -> Dict[str, Any]:

        try:
            start_time = __import__('time').time()


            if use_ai and self.llm:
                candidates = self.ai_search(job_description, limit=limit)
                search_type = "ai"
            else:
                candidates = self.basic_search(job_description, limit=limit)
                search_type = "basic"


            common_skills = ["python", "java", "javascript", "react", "angular", "vue", "node.js",
                             "django", "flask", "fastapi", "sql", "nosql", "mongodb", "aws", "azure",
                             "gcp", "docker", "kubernetes", "ci/cd", "agile", "scrum", "machine learning",
                             "data science", "ai", "product management", "ux", "ui", "design"]

            job_skills = []
            for skill in common_skills:
                if skill.lower() in job_description.lower():
                    job_skills.append(skill)

            end_time = __import__('time').time()
            search_time = round(end_time - start_time, 2)


            return {
                "candidates": candidates,
                "metadata": {
                    "search_type": search_type,
                    "job_skills_identified": job_skills,
                    "total_candidates": len(candidates),
                    "search_time_seconds": search_time,
                    "job_description_length": len(job_description)
                }
            }

        except Exception as e:
            logger.error(f"Error in smart search: {e}")
            return {
                "candidates": [],
                "metadata": {
                    "error": str(e),
                    "search_type": "failed"
                }
            }

    def get_department_statistics(self) -> Dict[str, Any]:

        try:
            pipeline = [
                {"$group": {
                    "_id": "$department",
                    "count": {"$sum": 1},
                    "avg_score": {"$avg": "$resume_score"}
                }},
                {"$sort": {"count": -1}}
            ]

            results = list(self.collection.aggregate(pipeline))

            departments = []
            for dept in results:
                departments.append({
                    "name": dept["_id"] if dept["_id"] else "Unspecified",
                    "candidate_count": dept["count"],
                    "average_score": round(dept["avg_score"], 2) if "avg_score" in dept else 0
                })

            return {
                "total_candidates": self.collection.count_documents({}),
                "departments": departments
            }

        except Exception as e:
            logger.error(f"Error getting department statistics: {e}")
            return {
                "total_candidates": 0,
                "departments": [],
                "error": str(e)
            }

    def get_top_candidates(self, limit: int = 5) -> List[Dict[str, Any]]:

        try:
            top_users = self.collection.find({}).sort("resume_score", -1).limit(limit)

            candidates = []
            for user in top_users:
                candidates.append({
                    "user_id": str(user["_id"]),
                    "name": user.get("name", "N/A"),
                    "department": user.get("department", "N/A"),
                    "resume_score": user.get("resume_score", 0),
                    "linkedin": user.get("linkedin_link", ""),
                    "github": user.get("github_link", "")
                })

            return candidates

        except Exception as e:
            logger.error(f"Error getting top candidates: {e}")
            return []

    def refresh_index(self) -> bool:

        try:

            if os.path.exists(self.chroma_persist_directory):
                import shutil
                shutil.rmtree(self.chroma_persist_directory)


            self._initialize_vector_store()


            indexed_count = self.index_all_users()

            return indexed_count > 0

        except Exception as e:
            logger.error(f"Error refreshing index: {e}")
            return False