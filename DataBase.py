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
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
app = FastAPI()
DATABASE_URL = 'mysql+pymysql://root:@127.0.0.1:3306/pidevgymWeb'  # Replace with your actual database URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
class User(Base):
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

class Evenement(Base):
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

class Reservation(Base):
    __tablename__ = 'reservation'
    id = Column(Integer, primary_key=True)
    date_reservation = Column(DateTime, nullable=False)
    nom_evenement = Column(String(255), nullable=False)
    nom_participant = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    # Define a relationship to the User model
    user = relationship('User', backref='user_reservation')
    # Define a relationship to the Evenement model

class Favoris(Base):
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

class Recommendation(BaseModel):
    id: int
    nom_evenement: str
    date: str
    time: str
    image: str
    score: float

@app.get("/recommend/{user_id}", response_model=List[Recommendation])
async def recommend_events(user_id: int):
    session = SessionLocal()

    try:
        # Get user's past reservations
        user_reservations = session.query(Reservation.nom_evenement).filter_by(user_id=user_id).all()
        print(f"user_reservations: {user_reservations}")

        user_categories = {reservation.nom_evenement for reservation in user_reservations}

        # Find events in the same category that the user hasn't reserved yet
        recommended_events = session.query(Evenement).filter(Evenement.categorie.in_(user_categories)) \
                              .filter(~Evenement.nom_evenement.in_(user_reservations)).all()

        # Check if recommended_events is not empty
        if recommended_events:
            # Prioritize events based on other users' behaviors
            first_event, middle_event = prioritize_events(recommended_events, user_id)
            
            # Prepare the response
            recommended_events = []

            if first_event and first_event[1] is not None:
                image = base64.b64encode(first_event[0].image).decode('utf-8') if first_event[0].image else None

                recommended_events.append({
                    'id': first_event[0].id,
                    'nom_evenement': first_event[0].nom_evenement,
                    'date': first_event[0].date.strftime('%Y-%m-%d'),
                    'time': str(first_event[0].time),  # Use str function
                    'image': image,
                    'score': first_event[1]
                })

            if middle_event and middle_event[1] is not None:
                image = base64.b64encode(middle_event[0].image).decode('utf-8') if middle_event[0].image else None

                recommended_events.append({
                    'id': middle_event[0].id,
                    'nom_evenement': middle_event[0].nom_evenement,
                    'date': middle_event[0].date.strftime('%Y-%m-%d'),
                    'time': str(middle_event[0].time),  # Use str function
                    'image': image,
                    'score': middle_event[1]
                })

        else:
            print("No recommended events found for this user.")

        return recommended_events

    finally:
        session.close()

def prioritize_events(recommended_events, user_id, user_reservations):
    session = SessionLocal()

    # Fetch all events that the user hasn't reserved yet
    candidate_events = [event.id for event in recommended_events]

    # Fetch the events and set score to 70 for all events
    events = session.query(
        Evenement,
        func.literal(70).label('score')  # Set score to 70 for all events
    ).filter(
        Evenement.id.in_(candidate_events),
        Evenement.nom_evenement.notin_(user_reservations)  # Exclude events the user has already reserved
    ).all()

    middle_index = len(events) // 2

    # Return the first event and the middle event
    first_event = events[0] if events else None
    middle_event = events[middle_index] if events else None
    session.close()
    return first_event, middle_event

@app.get("/run_recommendation")
async def run_recommendation():
    # Call your recommendation function here
    prioritize_events(recommended_events, user_id)
    return {"message": "recommendation executed successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)