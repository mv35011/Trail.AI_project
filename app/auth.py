from flask import Flask, request, redirect, render_template
from utils.profile_score import ResumeScorer
from dotenv import load_dotenv
import os
import datetime
from pymongo import MongoClient
from utils.preprocess import generate_unique_filename
from werkzeug.utils import secure_filename

mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client['users']
users_collection = db['users']
load_dotenv()


groq_api_key = os.getenv('GROQ_API_KEY')
auth = Flask(__name__)

auth.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    dept = request.form['department']
    cgpa = request.form['cgpa']
    skills = request.form.getlist('skills')
    resume = request.files['resume']
    about_yourself = request.form['about_yourself']
    linkedin = request.form['Linkedin']
    github = request.form['github']
    profile_image = request.files['profile_image']
    file_name = secure_filename(profile_image.filename)
    profile_path = os.path.join('media/ProfileImage', file_name)
    profile_image.save(profile_path)

    unique_name= generate_unique_filename(name, secure_filename((resume.filename)))
    resume_path = os.path.join('media/resume', unique_name)
    resume.save(resume_path)

    scorer = ResumeScorer(groq_api_key=groq_api_key, resume_pdf_path=resume_path)
    score = scorer.run_scorer()

    user_data = {
        "name":name,
        "email": email,
        "linkedin": linkedin,
        "github": github,
        "profile_image": profile_image,
        "department": dept,
        "cgpa":cgpa,
        "skills":skills,
        "resume_path":resume_path,
        "about_yourself":about_yourself,
        "resume_score": score,

    }
    users_collection.insert_one(user_data)
    return redirect('/dashboard')
