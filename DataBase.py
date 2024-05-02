from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import PickleType
from sqlalchemy import func
from flask import Flask, jsonify
import base64  # Add this line to import base64 module
from flask import render_template_string

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@127.0.0.1:3306/pidevgymWeb'
db = SQLAlchemy(app)

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String(180), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    is_verified = Column(Boolean, default=False)
    nom = Column(String(255), nullable=False)
    telephone = Column(Integer, nullable=False)
    image = Column(String(255), nullable=True)
    roles = Column(MutableList.as_mutable(PickleType), server_default='{}')
    # Define a relationship to the Favoris model
    favoris = relationship('Favoris', backref='user_favoris', cascade='all, delete-orphan')
    # Define a relationship to the Evenement model
    evenements = relationship('Evenement', backref='user_evenements', cascade='all, delete-orphan')
    # Define a relationship to the Reservation model
    reservations = relationship('Reservation', backref='user_reservations', cascade='all, delete-orphan')

class Evenement(db.Model):
    __tablename__ = 'evenement'
    id = Column(Integer, primary_key=True)
    nom_evenement = Column(String(255), nullable=False, unique=True)
    date = Column(DateTime, nullable=False)
    nbr_place = Column(Integer, nullable=False)
    categorie = Column(String(255), nullable=False)
    objectif = Column(String(255), nullable=False)
    etat = Column(Boolean, nullable=True)
    time = Column(DateTime, nullable=False)
    image = Column(LargeBinary)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    # Define a relationship to the User model
    user = relationship('User', backref='user_evenement')
    # Define a relationship to the Favoris model
    favoris = relationship('Favoris', backref='evenement_favoris')
    # Define a relationship to the Reservation model

class Reservation(db.Model):
    __tablename__ = 'reservation'
    id = Column(Integer, primary_key=True)
    date_reservation = Column(DateTime, nullable=False)
    nom_evenement = Column(String(255), nullable=False)
    nom_participant = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    # Define a relationship to the User model
    user = relationship('User', backref='user_reservation')
    # Define a relationship to the Evenement model

class Favoris(db.Model):
    __tablename__ = 'favoris'
    id = Column(Integer, primary_key=True)
    loved = Column(Boolean, nullable=False)
    unloved = Column(Boolean, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    evenement_id = Column(Integer, ForeignKey('evenement.id'), nullable=False)
    # Define a relationship to the User model
    user = relationship('User', backref='user_favoris')
    # Define a relationship to the Evenement model
    evenement = relationship('Evenement', backref='evenement_favoris')

@app.route('/recommend/<int:user_id>')
def recommend_events(user_id):
    # Get user's past reservations
    user_reservations = db.session.query(Reservation.nom_evenement).filter_by(user_id=user_id).all()
    user_categories = {reservation.nom_evenement for reservation in user_reservations}

    # Find events in the same category that the user hasn't reserved yet
    recommended_events = db.session.query(Evenement).filter(Evenement.categorie.in_(user_categories)) \
                          .filter(~Evenement.nom_evenement.in_(user_reservations)).all()

    # Prioritize events based on other users' behaviors
    first_event, middle_event = prioritize_events(recommended_events, user_id)

    # Prepare the response
    recommended_events = []

    if first_event:
        image = base64.b64encode(first_event[0].image).decode('utf-8') if first_event[0].image else None

        recommended_events.append({
            'id': first_event[0].id,
            'nom_evenement': first_event[0].nom_evenement,
            'date': first_event[0].date.strftime('%Y-%m-%d'),
            'time': str(first_event[0].time),  # Use str function
            'image': image,
            'score': first_event[1]
            
        })

    if middle_event:
        image = base64.b64encode(middle_event[0].image).decode('utf-8') if middle_event[0].image else None

        recommended_events.append({
            'id': middle_event[0].id,
            'nom_evenement': middle_event[0].nom_evenement,
            'date': middle_event[0].date.strftime('%Y-%m-%d'),
            'time': str(middle_event[0].time),  # Use str function
            'image': image,
            'score': middle_event[1]
        })

    return jsonify(recommended_events)

def prioritize_events(recommended_events, user_id):
    # Fetch all events that the user hasn't reserved yet
    user_reservations = db.session.query(Reservation.nom_evenement).filter_by(user_id=user_id).subquery()
    candidate_events = [event.id for event in recommended_events]

    # Calculate scores for each event based on other users' behaviors
    event_scores = db.session.query(
    Evenement,
        (func.count(Reservation.id) * 0.6 + func.sum(Favoris.loved.cast(Integer)) * 0.4).label('score')
    ).join(
        Favoris, Favoris.evenement_id == Evenement.id
    ).join(
        Reservation, Reservation.nom_evenement == Evenement.nom_evenement
    ).filter(
        Evenement.id.in_(candidate_events)
    ).group_by(
        Evenement.id
    ).subquery()

    # Fetch the events and their scores
    events = db.session.query(
        Evenement,
        event_scores.c.score
    ).outerjoin(
        event_scores, Evenement.id == event_scores.c.id
    ).order_by(
        event_scores.c.score.desc()
    ).all()

    middle_index = len(events) // 2

    # Return the first event and the middle event
    first_event = events[0] if events else None
    middle_event = events[middle_index] if events else None

    return first_event, middle_event

def home():
    evenements = Evenement.query.all()
    result = ''
    for evenement in evenements:
        image = base64.b64encode(evenement.image).decode('utf-8') if evenement.image else None
        result += f'<p>ID: {evenement.id}, Name: {evenement.nom_evenement}</p>'
        if image:
            result += f'<img src="data:image/jpeg;base64,{image}" alt="Event image">'
    return render_template_string(result)

if __name__ == "__main__":
    app.run(debug=True)