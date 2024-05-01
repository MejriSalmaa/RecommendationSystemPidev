class Evenement(db.Model):
    __tablename__ = 'evenement'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    evenements = Evenement.query.all()
    for evenement in evenements:
     print(evenement.id, evenement.name)