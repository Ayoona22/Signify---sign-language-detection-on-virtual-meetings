import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import tensorflow as tf
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load the gesture recognition model
try:
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'models', 'hand_gesture_model.h5')
    if os.path.exists(model_path):
        gesture_model = tf.keras.models.load_model(model_path)
    else:
        print(f"Model file not found at: {model_path}")
        gesture_model = None
except Exception as e:
    print(f"Error loading model: {e}")
    gesture_model = None

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    meetings = db.relationship('Meeting', backref='host', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Meeting model
class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meeting_code = db.Column(db.String(10), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    @staticmethod
    def generate_meeting_code():
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Meeting.query.filter_by(meeting_code=code).first():
                return code

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('signup'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's meetings
    meetings = Meeting.query.filter_by(host_id=current_user.id).all()
    return render_template('dashboard.html', meetings=meetings)

@app.route('/create-meeting', methods=['POST'])
@login_required
def create_meeting():
    title = request.form.get('title')
    if not title:
        flash('Meeting title is required', 'error')
        return redirect(url_for('dashboard'))
    
    meeting = Meeting(
        meeting_code=Meeting.generate_meeting_code(),
        title=title,
        host_id=current_user.id
    )
    db.session.add(meeting)
    db.session.commit()
    
    flash('Meeting created successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/join-meeting', methods=['POST'])
@login_required
def join_meeting():
    meeting_code = request.form.get('meeting_code')
    meeting = Meeting.query.filter_by(meeting_code=meeting_code).first()
    
    if not meeting:
        flash('Invalid meeting code', 'error')
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('meeting', code=meeting_code))

@app.route('/meeting/<code>')
@login_required
def meeting(code):
    meeting = Meeting.query.filter_by(meeting_code=code).first_or_404()
    return render_template('meeting_room.html', meeting=meeting)

@app.route('/predict_gesture', methods=['POST'])
def predict_gesture():
    if gesture_model is None:
        return jsonify({
            'error': 'Gesture recognition model not loaded'
        }), 500
        
    try:
        data = request.json
        landmarks = np.array(data['landmarks'])
        # Flatten the landmarks array first
        landmarks = landmarks.flatten()
        # Now reshape to match the model's expected shape (1, 30, 63)
        landmarks = landmarks.reshape((1, 30, 63))
        prediction = gesture_model.predict(landmarks)
        gesture_index = np.argmax(prediction[0])
        
        gesture_messages = [
            "I really appreciate it",
            "We all are with you",
            "Where are you from",
            "You are welcome",
        ]
        
        return jsonify({
            'gesture': gesture_messages[gesture_index],
            'confidence': float(prediction[0][gesture_index])
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

# Socket.IO events
@socketio.on('join')
def on_join(data):
    username = current_user.username
    room = data['room']
    join_room(room)
    emit('user_joined', {'username': username}, room=room)

@socketio.on('leave')
def on_leave(data):
    username = current_user.username
    room = data['room']
    leave_room(room)
    emit('user_left', {'username': username}, room=room)

@socketio.on('offer')
def on_offer(data):
    emit('offer', data, room=data['room'], include_self=False)

@socketio.on('answer')
def on_answer(data):
    emit('answer', data, room=data['room'], include_self=False)

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    emit('ice_candidate', data, room=data['room'], include_self=False)

@socketio.on('toggle_video')
def on_toggle_video(data):
    emit('video_toggled', {
        'userId': current_user.id,
        'username': current_user.username,
        'isVideoOn': data['isVideoOn']
    }, room=data['room'])

@socketio.on('toggle_audio')
def on_toggle_audio(data):
    emit('audio_toggled', {
        'userId': current_user.id,
        'username': current_user.username,
        'isAudioOn': data['isAudioOn']
    }, room=data['room'])

@socketio.on('chat_message')
def on_chat_message(data):
    emit('chat_message', {
        'userId': current_user.id,
        'username': current_user.username,
        'message': data['message'],
        'timestamp': data['timestamp']
    }, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True) 