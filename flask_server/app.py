import os
from flask import Flask, url_for, jsonify, redirect, render_template, request, abort, g
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user
from flask_security.utils import encrypt_password
import flask_admin
from flask_admin.contrib import sqla
from flask_admin.contrib.sqla import ModelView
from flask_admin import helpers as admin_helpers

from datetime import datetime

# Create Flask application
app = Flask(__name__)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)



##########################################################################################
############################        DataBase Models         ##############################
##########################################################################################

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('roles.id'))
)


class Role(db.Model, RoleMixin):
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name


#position - guest, student, teacher, stuff, admin 
class AccessGroup(db.Model):
    __tablename__ = 'accessGroups'
    id          = db.Column(db.Integer(), primary_key=True)
    position    = db.Column(db.String(100), nullable=False)
    
    users       = db.relationship('User',          backref='accessLevel')
    equipments  = db.relationship('EquipmentInst', backref='accessGroup')



class SharingBoxStation(db.Model):
    __tablename__ = 'stations'
    id = db.Column(db.Integer(), primary_key=True)
    # put station data here
    equipments  = db.relationship('EquipmentInst', backref='station')
    rents       = db.relationship('Rent',          backref='station')

    
    
class EquipmentType(db.Model):
    __tablename__ = 'equipmentTypes'
    id              = db.Column(db.Integer(),   primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    description     = db.Column(db.String(1000))
    pic_link        = db.Column(db.String(100))
    
    instances   = db.relationship('EquipmentInst', backref='type')



class EquipmentInst(db.Model):
    __tablename__ = 'equipments'
    id              = db.Column(db.Integer(), primary_key=True)
    stock_num       = db.Column(db.Integer(), unique=True)
    type_id         = db.Column(db.Integer(), db.ForeignKey('equipmentTypes.id'))
    station_id      = db.Column(db.Integer(), db.ForeignKey('stations.id'))
    accessGroup_id  = db.Column(db.Integer(), db.ForeignKey('accessGroups.id'))
    
    rents               = db.relationship('Rent',               backref='equipment')
    specialAccessRights = db.relationship('SpecialAccessRight', backref='equipment')



class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id          = db.Column(db.Integer(),   primary_key=True)
    first_name  = db.Column(db.String(100)) #, nullable=False)
    last_name   = db.Column(db.String(100)) #, nullable=False)
    patronymic  = db.Column(db.String(100))
    birthday    = db.Column(db.DateTime())
    login       = db.Column(db.String(80),  unique=True)
    email       = db.Column(db.String(120), unique=True)
    phone_num   = db.Column(db.String(30))
    password    = db.Column(db.String(64),  nullable=False)
    #auth2Token
    #role
    accessGroup_id = db.Column(db.Integer(),    db.ForeignKey('accessGroups.id'))
    rfid_uid       = db.Column(db.Integer(),    unique=True)
    created_time   = db.Column(db.DateTime(),   default=datetime.utcnow)
    last_login     = db.Column(db.DateTime(),   default=datetime.utcnow)
    
    rents               = db.relationship('Rent', backref='user') 
    specialAccessRights = db.relationship('SpecialAccessRight', backref='user')
    #granted             = db.relationship('SpecialAccessRight', backref='granter')########################

    ##############################
    active          = db.Column(db.Boolean())
    confirmed_at    = db.Column(db.DateTime())
    roles           = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __str__(self):
        return self.email
    ##############################
        
    # Flask-Login integration
    # NOTE: is_authenticated, is_active, and is_anonymous
    # are methods in Flask-Login < 0.3.0
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    # Required for administrative interface
    def __unicode__(self):
        return self.username

    #returns a list of dicts - with user's openedRents
    def getOpenRents(self, station_ID:int):
        out = []
        for x in self.rents:
            if x.end_time == None and int(x.station_id) == int(station_ID):
                out.append(dict(rent_id=x.id, equipment_id=x.equipment_id, station_id=x.station_id))
        return out



class SpecialAccessRight(db.Model):
    __tablename__ = 'specialAccessRights'
    user_id             = db.Column(db.Integer(),  db.ForeignKey('users.id'), primary_key=True)
    equipment_id        = db.Column(db.Integer(),  db.ForeignKey('equipments.id'), primary_key=True)
    accessGrantedDate   = db.Column(db.DateTime(), default=datetime.utcnow)
    #granter_id          = db.Column(db.Integer(),  db.ForeignKey('users.id'))##################################



class Rent(db.Model):
    __tablename__ = 'rents'
    id              = db.Column(db.Integer(), primary_key=True)
    user_id         = db.Column(db.Integer(), db.ForeignKey('users.id'))
    station_id      = db.Column(db.Integer(), db.ForeignKey('stations.id'))
    equipment_id    = db.Column(db.Integer(), db.ForeignKey('equipments.id'))
    begin_time      = db.Column(db.DateTime(), default=datetime.utcnow)
    end_time        = db.Column(db.DateTime(), default=None, onupdate=datetime.utcnow)
    
    def is_active(self):
        return (self.end_time == None)
    
    def get_id(self):
        return self.id







##########################################################################################
############################         Flask Security         ##############################
##########################################################################################


# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


##########################################################################################
############################          Flask Views           ##############################
##########################################################################################

def my_response(content=None, error=None, code=200):
    if content is None:
        content = {}
    content.update({"error": error, "is_ok": True if code == 200 else False})
    return jsonify(content), code

class ValidationError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code

@app.errorhandler(ValidationError)
def handle_database_error(e):
    return my_response(error=str(e), code=e.code)

# @app.errorhandler(sqlite3.DatabaseError)
# def handle_database_error(e):
    # if isinstance(e, sqlite3.IntegrityError):
        # return my_response(error=str(e), code=400)

    # return my_response(error=str(e), code=500)





# Flask views
@app.route('/')
def index():
    return render_template('index.html')


def searchUserBy_RFID_ID(RFID_UID: int):
    user = db.session.query(User).filter(User.rfid_uid == RFID_UID).first()
    print(user)
    return user

def searchUserBy_ID(user_id: int):
    user = db.session.query(User).filter(User.id == id).first()
    print(user)
    return user

def searchRentBy_ID(rent_id:int):
    rent = db.session.query(Rent).filter(Rent.id==rent_id).first()
    return rent
    
    
    
    # 1) search user in db by rfid_id
    # 2) if there is no user, return {} - empty
    # 3) else search for open rents of the user

@app.route('/stations/<station_id>/getUserData/<rfid_uid>', methods=['GET'])
#@login_required #Actual JUST FOR CONCRETE STATION. NO USER USE.
def getUserData(station_id: int, rfid_uid: int):
    user = searchUserBy_RFID_ID(rfid_uid)
    if user == None:
        raise ValidationError("User with rfid_id=%s not found" % rfid_uid, code=204)
        #return '{}'
    else:
        openRents = user.getOpenRents(station_id)
        print(openRents)###################################################################
        res = dict(user_id=user.id,
                   user_name=user.last_name+' '+user.first_name,
                   rents=openRents)
    return my_response(res)





@app.route('/stations/<station_id>/rents', methods=['POST']) #Open_rent
#@login_required 
def openRent(station_id:int):
    if not request.is_json:
        return my_response(error="Body should contains JSON", code=400)

    if "equipment_id" not in request.json:
        return my_response(error="Request should contains equipment_id", code=400)
    else:
        equipment_id = request.json["equipment_id"]

    if "user_id" in request.json:
        user = searchUserBy_ID(request.json["user_id"])
    elif "rfid_id" in request.json:
        user = searchUserBy_RFID_ID(request.json["rfid_id"])
    else:
        return my_response(error="Request should contains rfid_id or user_id", code=400)

    # \toDo
    #Check station_id, equipment_id, user_id
    #Check if there is the equipment in the station etc.
    #CHECK USER RIGHTS for renting THE EQUIPMENT
    
    rent = Rent()
    rent.user_id = user.id
    rent.station_id = station_id
    rent.equipment_id = equipment_id
    rent.begin_time = datetime.utcnow() #need? there is default data in db model
    rent.end_time = None
    
    db.session.add(rent)
    db.session.commit()
   
    print(rent.id)
    #openRents = user.getOpenRents(station_id)
   
    return my_response({"rent_id": rent.id})



@app.route('/stations/<station_id>/rents/<rent_id>', methods=['PUT']) #Close_rent
#@login_required 
def closeRent(station_id:int, rent_id:int):
    res={}
    rent = searchRentBy_ID(rent_id)
    if rent == None:
        raise ValidationError("Rent with rent_id=%s not found" % rent_id, code=404)
    else:
        if rent.end_time != None:
            raise ValidationError("Rent with rent_id=%s was already closed" % rent_id, code=404)
        rent.end_time = datetime.utcnow()
        db.session.add(rent)
        db.session.commit()
    return my_response({"error": 'OK'})
    
    
    
    
    
##########################################################################################
############################       Admin Panel Views        ##############################
##########################################################################################


# Create customized model view class
class MyModelView(sqla.ModelView):
    def is_accessible(self):
        return (current_user.is_active and
                current_user.is_authenticated and
                current_user.has_role('superuser')
        )

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for('security.login', next=request.url))



# Create admin
admin = flask_admin.Admin(
    app,
    'SharingBox',
    base_template='my_master.html',
    template_mode='bootstrap3',
)

# Add model views
admin.add_view(MyModelView(Rent, db.session))
admin.add_view(MyModelView(User, db.session))
admin.add_view(MyModelView(EquipmentType, db.session))
admin.add_view(MyModelView(EquipmentInst, db.session))
admin.add_view(ModelView(SharingBoxStation, db.session))
admin.add_view(MyModelView(Role, db.session))
admin.add_view(MyModelView(SpecialAccessRight, db.session))
admin.add_view(MyModelView(AccessGroup, db.session))

# define a context processor for merging flask-admin's template context into the
# flask-security views.
@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
        get_url=url_for
    )





##########################################################################################
############################         FillData in DB         ##############################
##########################################################################################



def build_rolesT():
    user_role = Role(name='user')
    super_user_role = Role(name='superuser')
    db.session.add(user_role)
    db.session.add(super_user_role)
    db.session.commit()
    return
     
def build_accessGroupsT():
    print("> accessGroups")
    i=1
    for role in ['guest', 'student', 'teacher', 'stuff', 'admin']:
        ag = AccessGroup()
        #ag.id = i
        i+=1
        ag.position = role
        db.session.add(ag)
    db.session.commit()
    return
  
def build_stationsT():
    st1 = SharingBoxStation()
    st2 = SharingBoxStation()
    db.session.add(st1)
    db.session.add(st2)
    
    db.session.commit()
    return
    
def build_equipmentTypesT():
    i=1
    for name in ['Ноутбук','Провод HDMI','Пульт ДУ']:
        eqType = EquipmentType()
        #eqType.id=i
        i+=1
        eqType.name = name
        db.session.add(eqType)
    db.session.commit()
    return
    
def build_equipmentsT():
    for i in range(3):
        eq = EquipmentInst()
        #eq.id               = i
        eq.stock_num        = i
        eq.type_id          = i
        eq.station_id       = 1
        eq.accessGroup_id   = 1 
        db.session.add(eq)
    db.session.commit()
    return
    
    ###tmp_pass = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(10))
def build_usersT():
    import string
    import random
    with app.app_context():    
        user_role = Role(name='user')
        super_user_role = Role(name='superuser')
        

        admin_user = User(          #user_datastore.create_user(
            first_name='Admin',
            last_name='admin',
            patronymic='admin',
            login='admin',
            email='admin',
            accessGroup_id=5,
            rfid_uid=200,
            password=encrypt_password('admin'),
            roles=[user_role, super_user_role]
        )
        db.session.add(admin_user)    
            
        test_user = User(                       #user_datastore.create_user(
                         first_name="Артём",
                         last_name="Потапов",
                         patronymic="Константинович",
                         login="mainCucumber", 
                         email="potapov@gmail.com",
                         password=encrypt_password("12345678"),
                         accessGroup_id=5,
                         rfid_uid=100,
                         roles=[user_role, super_user_role]
        )
        db.session.add(test_user)

        first_names = [
            'Harry', 'Amelia', 'Oliver', 'Jack', 'Isabella', 'Charlie','Sophie', 'Mia',
            'Jacob', 'Thomas', 'Emily', 'Lily', 'Ava', 'Isla', 'Alfie', 'Olivia', 'Jessica',
            'Riley', 'William', 'James', 'Geoffrey', 'Lisa', 'Benjamin', 'Stacey', 'Lucy'
        ]
        last_names = [
            'Brown', 'Smith', 'Patel', 'Jones', 'Williams', 'Johnson', 'Taylor', 'Thomas',
            'Roberts', 'Khan', 'Lewis', 'Jackson', 'Clarke', 'James', 'Phillips', 'Wilson',
            'Ali', 'Mason', 'Mitchell', 'Rose', 'Davis', 'Davies', 'Rodriguez', 'Cox', 'Alexander'
        ]

        for i in range(len(first_names)):
            user = User()
            user.first_name = first_names[i]
            user.last_name  = last_names[i]
            user.patronymic = 'X'
            user.login = user.first_name.lower()
            user.email = user.login + "@example.com"
            user.password = encrypt_password(first_names[i]+last_names[i])
            user.accessGroup_id = 1
            user.rfid_uid = i
            user.roles=[user_role, ]
            
            #user_datastore.add_user(user)
            db.session.add(user)

        db.session.commit()
    return

def build_sample_db():
    
    db.drop_all()
    db.create_all()
    build_accessGroupsT()
    build_stationsT()
    build_equipmentTypesT()
    build_equipmentsT()
    build_usersT()
    


##########################################################################################
############################          Launch mode           ##############################
##########################################################################################


if __name__ == '__main__':

    # Build a sample db on the fly, if one does not exist yet.
    app_dir = os.path.realpath(os.path.dirname(__file__))
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db()

    # Start app
    app.run(debug=True)
