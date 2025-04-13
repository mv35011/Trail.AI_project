from flask import Flask,flash, request, redirect, render_template, Blueprint, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from app.utils.profile_score import ResumeScorer
from dotenv import load_dotenv
import os
import datetime
from pymongo import MongoClient
from app.utils.preprocess import generate_unique_filename
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import uuid
from app.utils.AI_Search_Engine import SearchEngine
load_dotenv()

auth = Blueprint('auth', __name__)
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client['users']
users_collection = db['users']


login_manager = LoginManager()

login_manager.login_view = 'auth.login'

groq_api_key = os.getenv('GROQ_API_KEY')
search_engine = SearchEngine(mongodb_uri= mongo_uri, groq_api_key=groq_api_key )
UPLOAD_FOLDERS = {
    'profile_images': 'media/ProfileImage',
    'resumes': 'media/resume'
}
for folder in UPLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get('_id'))
        self.name = user_data.get('name')
        self.email = user_data.get('email')
        self.role = user_data.get('role', 'student')
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

def generate_unique_filename(name, filename):

    name_part = name.lower().replace(' ', '_')
    extension = os.path.splitext(filename)[1]
    unique_id = uuid.uuid4().hex[:8]
    return f"{name_part}_{unique_id}{extension}"
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        if not all([email, password, role]):
            flash('All fields are required', 'error')
            return render_template('login.html')


        if role != 'student':
            flash('Only student login is available at this time', 'error')
            return render_template('login.html')
        user_data = users_collection.find_one({'email':email})

        if user_data and check_password_hash(user_data.get('password', ''), password):
            user = User(user_data)
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    return render_template('login.html')




@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:

            name = request.form.get('studentName')
            college_name = request.form.get('collegeName')
            email = request.form.get('collegeEmail')
            skills_text = request.form.get('skills')
            about_yourself = request.form.get('aboutYourself')
            resume = request.files.get('resume')
            password = request.form.get('password')
            confirm_password = request.form.get('confirmPassword')


            dept = request.form.get('department', 'Not specified')
            cgpa = request.form.get('cgpa', '0.0')
            linkedin = request.form.get('linkedin', '')
            github = request.form.get('github', '')


            if 'profile_image' in request.files and request.files['profile_image'].filename != '':
                profile_image = request.files['profile_image']
            else:

                from werkzeug.datastructures import FileStorage
                import io
                profile_image = FileStorage(
                    stream=io.BytesIO(b'placeholder'),
                    filename='default_profile.png',
                    content_type='image/png',
                )


            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')


            if users_collection.find_one({'email': email}):
                flash('Email already registered', 'error')
                return render_template('register.html')


            skills = [skill.strip() for skill in skills_text.split(',') if skill.strip()]


            file_name = secure_filename(profile_image.filename)
            profile_path = os.path.join(UPLOAD_FOLDERS['profile_images'], file_name)
            profile_image.save(profile_path)


            unique_name = generate_unique_filename(name, secure_filename(resume.filename))
            resume_path = os.path.join(UPLOAD_FOLDERS['resumes'], unique_name)
            resume.save(resume_path)


            scorer = ResumeScorer(groq_api_key=groq_api_key, resume_pdf_path=resume_path)
            score = scorer.run_scorer()


            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            with open(resume_path, 'rb') as f:
                resume_binary = f.read()

            user_data = {
                "name": name,
                "college_name": college_name,
                "email": email,
                "linkedin": linkedin,
                "github": github,
                "profile_image": profile_path,
                "department": dept,
                "cgpa": cgpa,
                "skills": skills,
                "resume_path": resume_path,
                "resume_pdf": resume_binary,
                "about_yourself": about_yourself,
                "resume_score": score,
                "password": hashed_password,
                "role": "student"
            }

            #Insert user to database
            result = users_collection.insert_one(user_data)

            if result.inserted_id:

                search_engine.index_user(result.inserted_id)

                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Registration failed. Please try again.', 'error')

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')

@auth.route('/sign-up-as-student')
def sign_up_asstudent():
    return render_template('signupasstudent.html')
@auth.route('/sign-up-as-recruiter')
def sign_up_asrecruiter():
    return render_template('signupasrecruiter.html')