import time
import uuid


def generate_unique_filename(username, filename):
    timestamp = int(time.time())
    ext = filename.split('.')[-1]
    return f"{username}_{timestamp}.{ext}"


def get_safe_resume_filename(base_name):
    ext = base_name.split('.')[-1]
    return f"{base_name.split('.')[0]}_{uuid.uuid4().hex[:8]}.{ext}"