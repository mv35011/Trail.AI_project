from flask import Blueprint, render_template, send_from_directory, request, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid


load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client['users']
users_collection = db['users']
views = Blueprint('views',__name__)





@views.route('/')
def home():
    return render_template('home.html')

@views.route('/preview_resume/<filename>')
def preview_resume(filename):
    return send_from_directory('generated_resumes', filename)

@views.route('/replace_resume', methods=['POST'])
def replace_resume():
        email = request.form['email']
        new_resume_path = request.form['new_resume_path']
        new_score = int(request.form['resume_score'])

        user = users_collection.find_one({'email': email})
        if not user:
            return "User not found", 404

        old_resume_path = user.get('resume_path')
        if old_resume_path and os.path.exists(old_resume_path):
            os.remove(old_resume_path)
        final_name = f"{email.split('@')[0]}_{uuid.uuid4().hex[:8]}.pdf"
        final_path = os.path.join("media/resumes", final_name)

        os.rename(new_resume_path, final_path)
        users_collection.update_one(
            {'email': email},
            {'$set': {
                'resume_path': final_path,
                'resume_score': new_score
            }}
        )
        return redirect(url_for('dashboard'))

@views.route('/dashboard', methods=['POST', 'GET'])
def dashboard():
    sorted_users = list(users_collection.find().sort("resume_score", -1))
    return render_template("dashboard.html", users=sorted_users)
