from flask import send_file, jsonify,Flask,flash, request, redirect, render_template, Blueprint, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from app.utils.profile_score import ResumeScorer
from dotenv import load_dotenv
import os
import io
import datetime
from pymongo import MongoClient
from app.utils.preprocess import generate_unique_filename
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import uuid
from app.utils.AI_Search_Engine import SearchEngine
load_dotenv()
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

            try:
                scorer = ResumeScorer(groq_api_key=groq_api_key, resume_pdf_path=resume_path)
                score = scorer.run_scorer()
            except Exception as scorer_error:
                logger.error(f"Resume scoring failed: {scorer_error}")
               
                score = 75 
                flash('Resume scoring temporarily unavailable. Using default score.', 'warning')


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

            result = users_collection.insert_one(user_data)

            if result.inserted_id:
                try:
                 
                    search_engine.index_user(result.inserted_id)
                except Exception as index_error:
                    logger.error(f"User indexing failed: {index_error}")
                    flash('User registered successfully, but search indexing is temporarily unavailable.', 'warning')

              
                user = User(user_data)
                login_user(user)
                session['user_id'] = str(result.inserted_id)
                session['user_name'] = name

                flash('Registration successful!', 'success')
                return redirect(url_for('auth.dashboard'))
            else:
                flash('Registration failed. Please try again.', 'error')

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template('register.html')

    return render_template('register.html')


@auth.route('/dashboard')
@login_required
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))


    top_users = search_engine.get_top_candidates(limit=6)

    top_users = search_engine.get_top_candidates(limit=6)

    return render_template('dashboard.html',
                           user_name=current_user.name if current_user.is_authenticated else None,
                           top_users=top_users)


@auth.route('/profile/<user_id>')
def profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard'))

        user['_id'] = str(user['_id'])

        return render_template('profile.html',
                               user=user,
                               current_user_id=session.get('user_id'))
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        flash('An error occurred while fetching the profile', 'error')
        return redirect(url_for('dashboard'))

@auth.route('/search')
def search():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    query = request.args.get('query', '')
    use_ai = request.args.get('use_ai', 'false').lower() == 'true'

    if not query:
        return jsonify({'results': []})

    try:
        if use_ai:
    
            search_results = search_engine.smart_search(query, limit=5, use_ai=True)
            candidates = search_results.get('candidates', [])
        else:
         
            candidates = search_engine.basic_search(query, limit=5)

        results = []
        for candidate in candidates:
            results.append({
                'type': 'user',
                'id': candidate.get('user_id'),
                'name': candidate.get('name', 'N/A'),
                'title': candidate.get('department', 'N/A'),
                'score': candidate.get('match_score', 0)
            })

        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@auth.route('/tools/<tool_name>')
def tools(tool_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    valid_tools = ['resume-builder', 'career-roadmap', 'email-generator']
    if tool_name not in valid_tools:
        flash('Tool not found', 'error')
        return redirect(url_for('dashboard'))

    return render_template(f'tools/{tool_name}.html',
                          user_name=session.get('user_name'))


@auth.route('/download_resume/<user_id>')
def download_resume(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('auth.dashboard'))

        if 'resume_pdf' in user:
            resume_data = io.BytesIO(user['resume_pdf'])
            filename = os.path.basename(user.get('resume_path', 'resume.pdf'))
            return send_file(
                resume_data,
                download_name=filename,
                as_attachment=True,
                mimetype='application/pdf'
            )
        else:
            flash('Resume not found', 'error')
            return redirect(url_for('auth.profile', user_id=user_id))

    except Exception as e:
        logger.error(f"Error downloading resume: {e}")
        flash('An error occurred while downloading the resume', 'error')
        return redirect(url_for('auth.profile', user_id=user_id))

@auth.route('/logout')
def logout():
    session.clear()
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))
