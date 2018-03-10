from flask import Flask,request,render_template, g, flash, url_for, redirect, abort
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask.ext.wtf import Form
from wtforms import TextField
from wtforms import PasswordField
from wtforms.validators import Required
from flask_wtf.html5 import EmailField
from flask.ext.login import login_user, logout_user, current_user, login_required
import re
import pickle
import os

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)

import os
from flask.ext.login import LoginManager

lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'


class LoginForm(Form):
	username = TextField('Userame', validators = [Required()])
	password = PasswordField('Password', validators = [Required()])

class RegisterForm(Form):
	username = TextField('Userame', validators = [Required()])
	password = PasswordField('Password', validators = [Required()])
	password_again = PasswordField('Password again', validators = [Required()])
	mail = TextField('Mail', validators = [Required()])

class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(50), index=True, unique=True)
	password = db.Column(db.String(16))
	mail = db.Column(db.String(50))
	is_admin = db.Column(db.Boolean)
	is_ban = db.Column(db.Boolean)

	questionnaires = db.relationship("Questionnaire", backref='user', lazy='dynamic')
	quesanswers = db.relationship("QuesAnswer", backref='user', lazy='dynamic')

	def is_authenticated(self):
		return True

	def is_active(self):
		return True

	def is_anonymous(self):
		return False

	def get_id(self):
		return unicode(self.id)

	def __repr__(self):
		return '<User %r>' % (self.username)

class Questionnaire(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(100))
	subject = db.Column(db.String(100))
	description = db.Column(db.Text)
	create_time = db.Column(db.DateTime)
	schema = db.Column(db.PickleType)
	author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	is_ban = db.Column(db.Boolean)

	releases = db.relationship("Release", backref='questionnaire', lazy='dynamic')
	quesanswers = db.relationship("QuesAnswer", backref='questionnaire', lazy='dynamic')

	def get_status(self):
		if self.is_ban:
			return 'Banned'
		releases = list(self.releases)
		if not releases:
			return 'In creating'
		release = releases[-1]
		if release.get_status():
			if len(releases) > 1:
				return 'In reopening'
			else:
				return 'In releasing'
		return 'Closed'

	def get_last_release(self):
		releases = list(self.releases)
		if not releases:
			return None
		else:
			return releases[-1]


class Release(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	ques_id = db.Column(db.Integer, db.ForeignKey('questionnaire.id'))
	start_time = db.Column(db.DateTime)
	end_time = db.Column(db.DateTime)
	security = db.Column(db.PickleType)
	is_closed = db.Column(db.Boolean)

	def get_status(self):
		current_time = datetime.now()
		if current_time >= self.start_time and current_time <= self.end_time and not self.is_closed:
			return True
		else:
			return False

class QuesAnswer(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	ques_id = db.Column(db.Integer, db.ForeignKey('questionnaire.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	ip = db.Column(db.String(50))
	date = db.Column(db.DateTime)

	probanswers = db.relationship("ProbAnswer", backref='ques_answer', lazy='dynamic')

class ProbAnswer(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	ques_ans_id = db.Column(db.Integer, db.ForeignKey('ques_answer.id'))
	prob_id = db.Column(db.Integer)
	ans = db.Column(db.Text)


@app.route('/user/<string:username>')
@login_required
def user(username):
    users = list(User.query.filter_by(username = username))
    if not users:
        abort(404)
    user = users[0]
    created = Questionnaire.query.filter_by(author_id = user.id).all()
    created = list(created)
    releases = [list(x.releases)[-1] if list(x.releases) else None for x in created]  #retrive last release for each ques
    
    #only show last answers
    ques_answers = []
    ques_ans = {}
    for qa in user.quesanswers:
        ques_ans[qa.ques_id] = qa
    for q_id in ques_ans:
        ques_answers.append(ques_ans[q_id])
        
    
    return render_template('user.html',
            g = g,
            user = user,
            ques_list_created = created,
            ques_list_releases = releases,
            ques_ans_list = ques_answers)



def is_not_admin():
    user = g.user
    if not user or not user.is_admin:
        return True
    return False

@app.route('/administrator')
@login_required
def administrator():
    if is_not_admin():
        pass
    else:
        d = datetime.now()
        oneday = timedelta(days=1)
        questionnaires_week = []
        answer_week = []

        for i in range(7):
            date_from = datetime(d.year, d.month, d.day, 0, 0, 0)
            date_to = datetime(d.year, d.month, d.day, 23, 59, 59)
            questionnaires_week.append(
                (d.date(),
                Questionnaire.query.filter(
                Questionnaire.create_time >= date_from).filter(
                Questionnaire.create_time <= date_to).count()))
            answer_week.append(
                (d.date(),
                QuesAnswer.query.filter(
                QuesAnswer.date >= date_from).filter(
                QuesAnswer.date <= date_to).count()))
            d = d - oneday

        users = User.query.all()
        questionnaires = Questionnaire.query.all()

    return render_template('administrator.html',
        users = users,
        questionnaires = questionnaires,
        questionnaires_week = questionnaires_week,
        answer_week = answer_week)

@app.route('/administrator/ban_user/<int:userid>')
@login_required
def ban_user(userid):
    if is_not_admin():
        pass
    else:
        u = User.query.get(userid)
        if not u:
            flash("No such user",'error')
        elif u.is_ban:
            flash("The user has been banned",'error')
        else:
            u.is_ban = True
            db.session.add(u)
            db.session.commit()
            flash("Ban successfully")

    return redirect(url_for('administrator'))

@app.route('/administrator/unban_user/<int:userid>')
@login_required
def unban_user(userid):
    if is_not_admin():
        pass
    else:
        u = User.query.get(userid)
        if not u:
            flash("No such user",'error')
        elif not u.is_ban:
            flash("The user has been unbanned",'error')
        else:
            u.is_ban = False
            db.session.add(u)
            db.session.commit()
            flash("Unban successfully")

    return redirect(url_for('administrator'))

@app.route('/administrator/ban_questionnaire/<int:qid>')
@login_required
def ban_questionnaire(qid):
    if is_not_admin():
        pass
    else:
        q = Questionnaire.query.get(qid)
        if not q:
            flash("No such questionnaire",'error')
        elif q.is_ban:
            flash("The questionnaire has been banned",'error')
        else:
            q.is_ban = True
            db.session.add(q)
            db.session.commit()
            flash("Ban successfully")

    return redirect(url_for('administrator'))

@app.route('/administrator/unban_questionnaire/<int:qid>')
@login_required
def unban_questionnaire(qid):
    if is_not_admin():
        pass
    else:
        q = Questionnaire.query.get(qid)
        if not q:
            flash("No such questionnaire",'error')
        elif not q.is_ban:
            flash("The questionnaire has been unbanned",'error')
        else:
            q.is_ban = False
            db.session.add(q)
            db.session.commit()
            flash("Unban successfully")

    return redirect(url_for('administrator'))

@app.route('/questionnaire/<int:questionnaire_id>')
@login_required
def questionnaire(questionnaire_id):
    q = Questionnaire.query.get(questionnaire_id)
    if not q:
        return "ERROR!"
    elif q.get_status() == 'Banned':
            return render_template('message.html',
                message = 'Sorry, the questionnaire is banned')
    else:
        title = q.title
        subject = q.subject
        description = q.description

        release = None
        count = 0
        for r in q.releases:
            count += 1
            if not r.is_closed:
                release = r
                break

        start_time = None
        end_time = None
        is_allow_anonymous = None
        limit_num_participants = None
        limit_num_ip = None
        special_participants = ''
        if release:
            start_time = r.start_time
            end_time = r.end_time
            security = pickle.loads(r.security)
            is_allow_anonymous = security['anonymous']
            limit_num_participants = security['limit_per_user']
            limit_num_ip = security['limit_per_ip']
            if security['limit_participants']:
                special_participants = ', '.join(security['limit_participants'])
        state = q.get_status()

        ques_list = get_ques_list(q)

        pics = os.listdir('/Users/SuperFrank/Desktop/work/Plask-backup/Plask-master/app/static/img/'+q.description+"/")

        return render_template('questionnaire_report.html',
            questionnaire_id = questionnaire_id,
            title = title,
            subject = subject,
            description = description,
            state = state,
            start_time = start_time,
            end_time = end_time,
            is_allow_anonymous = is_allow_anonymous,
            limit_num_participants = limit_num_participants,
            limit_num_ip = limit_num_ip,
            special_participants = special_participants,
            q_id = questionnaire_id,
            ques_list = ques_list,
            ques = q,
            pics=pics)

@app.route('/questionnaire/<int:questionnaire_id>/release', methods = ['GET', 'POST'])
@login_required
def release(questionnaire_id):
    def get_security():
        def to_int(string):
            try: return int(string)
            except ValueError: return None
        
        security = {}

        if 'is_allow_anonymous' not in request.form:
            is_allow_anonymous = False
        else:
            is_allow_anonymous = True

        if 'limit_num_participants' not in request.form:
            limit_num_participants = None
        elif not request.form['limit_num_participants']:
            limit_num_participants = None
        else:
            limit_num_participants = to_int(request.form['limit_num_participants'])

        if 'limit_num_ip' not in request.form:
            limit_num_ip = None
        elif not request.form['limit_num_ip']:
              limit_num_ip = None
        else:
            limit_num_ip = to_int(request.form['limit_num_ip'])

        if 'special_participants' not in request.form:
            special_participants = None
        else:
            data = request.form['special_participants']
            if not data:
                special_participants = None
            else:
                special_participants = data.split(',')
                for i in special_participants:
                    i = i.strip()
                  

        security['anonymous'] = is_allow_anonymous
        security['limit_per_user'] = limit_num_participants
        security['limit_per_ip'] = limit_num_ip
        security['limit_participants'] = special_participants
          
        return security

    if request.method == 'POST':
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        if start_time <  end_time:
            security = get_security()
            dumped_security = pickle.dumps(security, protocol = 2)
            release = Release(ques_id = questionnaire_id,
                start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S'),
                end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S'),
                security = dumped_security,
                is_closed = False)
            db.session.add(release)
            db.session.commit()
            return render_template('release_success.html',
                g = g,
                q_id = questionnaire_id,
                message = 'Release successfully')
        else:
            flash("Start time is later then end time",'error')

    return render_template('release.html')

@app.route('/questionnaire/<int:questionnaire_id>/close', methods = ['GET'])
@login_required
def close(questionnaire_id):
    q = Questionnaire.query.get(questionnaire_id)
    release = None
    for r in q.releases:
        if not r.is_closed:
            release = r
            break
    if not release:
        flash("The release has been closed",'error')
    else:
        release.is_closed = True
        db.session.add(release)
        db.session.commit()
        flash("Close successfully")
  
    return redirect(url_for('questionnaire', questionnaire_id = questionnaire_id))

def get_ques_list(q):
    schema = pickle.loads(q.schema)
    ques_list = []
    for i in range(len(schema)):
        each = schema[i]
        dic = {}
        dic['description'] = each['description']
        dic['type'] = each['type']
        if each['type'] == '3':
            dic['option_list'] = []
        elif each['type'] == '2':
            dic['option_list'] = ['true', 'false']
            dic['num_list'] = [0,0]
        else:
            dic['option_list'] = each['options']
            dic['num_list'] = []
            for option in dic['option_list']:
                dic['num_list'].append(0)

        quesanswers = q.quesanswers.all()
        for quesanswer in quesanswers:
            answers = quesanswer.probanswers.filter_by(prob_id = i)
            if each['type'] == '3':
                for answer in answers:
                    dic['option_list'].append(answer.ans)
                print str(dic['option_list'])
            elif each['type'] == '2':
                for answer in answers:
                    if answer.ans=='1':
                        dic['num_list'][0] = dic['num_list'][0] + 1;
                    else:
                        dic['num_list'][1] = dic['num_list'][1] + 1;
            else:
                for answer in answers:
                    dic['num_list'][int(answer.ans)] = dic['num_list'][int(answer.ans)] + 1
        ques_list.append(dic)

    return ques_list




@app.route('/questionnaire/create', methods = ['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        q_title = request.form['title']
        q_subject = request.form['subject']
        q_description = request.form['description']
        q = Questionnaire(title = q_title,
                          subject = q_subject,
                          description = q_description,
                          )
        db.session.add(q)
        db.session.commit()
        return redirect(url_for('create_question',q_id=q.id))
    
    return render_template('questionnaire_create.html',
            g = g)
    

@app.route('/questionnaire/<int:q_id>/create_question',methods = ['GET','POST'])
@login_required
def create_question(q_id):
    def get_questions():
        questions = []
        current_index = 0
        while True:
            ques_form = 'ques_' + str(current_index)  #example: ques_1
            if ques_form+'.type' in request.form:
                current_question = {
                                    "type": request.form[ques_form + '.type'],  #example:ques_7.type 
                                    "description": request.form[ques_form + '.description'],    #example:ques_9.description
                                    "options": get_options(ques_form)
                                   }
                questions.append(current_question)
                current_index += 1
            else: break
        return questions
    
    def get_options(ques_form):
        options = []
        option_index = 0
        while True:
            option = ques_form + '.option_' + str(option_index)  #example: ques_3.option_3 'C.wow'
            if option in request.form: 
                options.append(request.form[option])
                option_index += 1
            else: break
        return options
                
    q = Questionnaire.query.get(q_id)
    if not q:
        return "ERROR!"
    if request.method == 'POST':
        questions = get_questions()
        dumped_questions = pickle.dumps(questions, protocol = 2)
        q.schema = dumped_questions
        q.create_time = datetime.now()
        q.author_id = g.user.id

        db.session.add(q)
        db.session.commit()
        return render_template('create_success.html',
                g = g,
                message = 'Questionnaire Created Successfully',
                q_id = q_id)
    
    return render_template('questionnaire_create_question.html',
            g = g)

@app.route('/questionnaire/<int:q_id>/fill',methods = ['GET','POST'])
def fill(q_id):

    

    q = Questionnaire.query.get(q_id)
    if not q:
        return "ERROR!"
    pics = os.listdir('/Users/SuperFrank/Desktop/work/Plask-backup/Plask-master/app/static/img/'+q.description+"/")

    #begin access control
    if q.get_status() == 'Banned':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is banned')
    if q.get_status() == 'Closed':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is closed')
    if q.get_status() == 'In creating':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is not ready yet')
    
    release = q.get_last_release()
    security = pickle.loads(release.security)

    if not security['anonymous'] and g.user is None:
        return render_template('message.html',
                message = 'Sorry, you can not access the questionnaire')
    
    if security['limit_per_user'] and g.user:
        limit = security['limit_per_user']
        already = QuesAnswer.query.filter_by(user_id = g.user.id).filter_by(ques_id = q_id).count()
        if already >= limit:
            return render_template('message.html',
                    message = 'Sorry, you can not access the questionnaire')
    
    if security['limit_per_ip']:
        limit = security['limit_per_ip']
        ip = request.remote_addr
        already = QuesAnswer.query.filter_by(ip = ip).filter_by(ques_id = q_id).count()
        if already >= limit:
            return render_template('message.html',
                    message = 'Sorry, you can not access the questionnaire')
    
    if security['limit_participants']:
        if not g.user or g.user.username not in security['limit_participants']:
            return render_template('message.html',
                    message = 'Sorry, you can not access the questionnaire')
    #end access control

    if request.method == 'GET':
        schema = pickle.loads(q.schema)
        return render_template('questionnaire_fill.html',
            g = g, 
            schema = schema,
            title = q.title,
            subject = q.subject,
            description = q.description,pics=pics)
    
    elif request.method == 'POST':
        questions = pickle.loads(q.schema)  
        ans = QuesAnswer(
                         ques_id = q.id,
                         user_id = g.user.id if g.user else None,
                         ip = request.remote_addr,
                         date = datetime.now()
                         )
        db.session.add(ans)
        db.session.commit()
        for prob_id in range(len(questions)):
            if questions[prob_id]['type'] in ['0','2','3']:
                #single-selection, true/false ,or essay question
                if ('ques_' + str(prob_id) + '.ans') not in request.form:
                    flash('Please fill in the blank', 'error')
                    return render_template('questionnaire_fill.html',
                        g = g, 
                        schema = questions,
                        title = q.title,
                        subject = q.subject,
                        description = q.description,pics=pics)
                else:
                    p_ans = ProbAnswer(ques_ans_id = ans.id,
                                        prob_id = prob_id,
                                        ans = request.form['ques_' + str(prob_id) + '.ans'],  #example: ques_3.ans 2(that is, C)
                                        )
                    db.session.add(p_ans)
            elif questions[prob_id]['type'] == '1':
                #multi-selection
                for choice_id in range(len(questions[prob_id]["options"])):
                    if 'ques_' + str(prob_id) + '.ans_' + str(choice_id) in request.form: #example: ques_4.ans_7 which is a checkbox
                        p_ans = ProbAnswer(ques_ans_id = ans.id,
                                           prob_id = prob_id,
                                           ans = str(choice_id),  
                                          )
                        db.session.add(p_ans)
        db.session.commit()
        return render_template('fill_success.html',
                g = g,
                message = 'Thank you for your paticipation')

@app.route('/questionnaire/<int:q_id>/preview')
def preview(q_id):
    q = Questionnaire.query.get(q_id)
    if not q:
        return "ERROR!"

    if q.get_status() == 'Banned':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is banned')

    schema = pickle.loads(q.schema)
    return render_template('questionnaire_preview.html',
            g = g,
            id = q.id,
            schema = schema,
            title = q.title,
            subject = q.subject,
            description = q.description)

@app.route('/questionnaire/<int:q_id>/modify', methods = ['GET', 'POST'])
@login_required
def modify(q_id):
    q = Questionnaire.query.get(q_id)
    if not q:
        return "ERROR!"

    if q.get_status() == 'Banned':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is banned')

    if q.quesanswers.count() > 0:
        return render_template('message.html',
                message = 'Sorry, the questionnaire already has answers. Please consider creating a new one')

    if request.method == 'POST':
        q_title = request.form['title']
        q_subject = request.form['subject']
        q_description = request.form['description']
        q.title = q_title
        q.subject = q_subject
        q.description = q_description
        db.session.add(q)
        db.session.commit()
        return redirect(url_for('modify_question',q_id=q.id))
    
    return render_template('questionnaire_modify.html',
            g = g,
            title = q.title,
            subject = q.subject,
            description = q.description)

@app.route('/questionnaire/<int:q_id>/modify_question',methods = ['GET','POST'])
@login_required
def modify_question(q_id):
    def get_questions():
        questions = []
        current_index = 0
        while True:
            ques_form = 'ques_' + str(current_index)  #example: ques_1
            if ques_form+'.type' in request.form:
                current_question = {
                                    "type": request.form[ques_form + '.type'], 
                                    "description": request.form[ques_form + '.description'],    #example:ques_9.description
                                    "options": get_options(ques_form)
                                   }
                questions.append(current_question)
                current_index += 1
            else: break
        return questions
    
    def get_options(ques_form):
        options = []
        option_index = 0
        while True:
            option = ques_form + '.option_' + str(option_index)  #example: ques_3.option_3 'C.wow'
            if option in request.form: 
                options.append(request.form[option])
                option_index += 1
            else: break
        return options
                
    q = Questionnaire.query.get(q_id)
    if not q:
        return "ERROR!"

    if q.get_status() == 'Banned':
        return render_template('message.html',
                message = 'Sorry, the questionnaire is banned')

    if q.quesanswers.count() > 0:
        return render_template('message.html',
                message = 'Sorry, the questionnaire already has answers. Please consider creating a new one')

    if request.method == 'POST':
        questions = get_questions()
        dumped_questions = pickle.dumps(questions, protocol = 2)
        q.schema = dumped_questions
        q.create_time = datetime.now()
        q.author_id = g.user.id

        db.session.add(q)
        db.session.commit()
        return render_template('create_success.html',
                g = g,
                message = 'Questionnaire Modified Successfully',
                q_id = q_id)
    
    schema = pickle.loads(q.schema)
    return render_template('questionnaire_modify_question.html',
            g = g,
            schema = schema)






@lm.user_loader
def load_user(id):
	return User.query.get(int(id))


@app.before_request
def before_request():
	if current_user.is_authenticated:
		g.user = current_user
	else:
		g.user = None


@app.route('/')
def index():
	if g.user is not None and g.user.is_authenticated():
		if g.user.is_admin == True:
			return redirect(url_for('administrator'))
		else:
			return redirect(url_for('user', username = g.user.username))
	
	return render_template("index.html")


@app.route('/login', methods = ['GET', 'POST'])
def login():
	if g.user is not None and g.user.is_authenticated():
		if g.user.is_admin == True:
			return redirect(url_for('administrator'))
		else:
			return redirect(url_for('user', username = g.user.username))

	form = LoginForm()
	
	if form.validate_on_submit():
		user = User.query.filter_by(username = form.username.data).first()
		if (user is not None and user.password == form.password.data and not user.is_ban):
			login_user(user)
			flash("Login successfully")
			if user.is_admin == True:
				return redirect(request.args.get('next') or url_for('administrator'))
			else:
				return redirect(request.args.get('next') or url_for('user', username = user.username))
		form.password.data = ''
		flash("Login failed",'error')
	
	return render_template('login.html',
		g = g,
		form = form,
		islogin = True)


@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('login'))

@app.route('/register', methods = ['GET', 'POST'])
def register():
	form = RegisterForm()

	if form.validate_on_submit():
		email_re = re.compile(r'\S+@\S+.\S+')
		if not email_re.match(form.mail.data):
			form.password.data = ''
			form.password_again.data = ''
			flash("Email format invalid",'error')
			return render_template('register.html',
					g = g,
					form = form)

		if form.password.data == form.password_again.data:
			user = User(
				username = form.username.data,
				password = form.password.data,
				mail = form.mail.data)
			try:
				db.session.add(user)
				db.session.commit()
			except:
				form.username.data = ''
				form.password.data = ''
				form.password_again.data = ''
				flash("The username has been used",'error')
				return render_template('register.html',
						g = g,
						form = form)
			login_user(user);
			flash("Register successfully")
			return redirect(url_for('user', username = user.username))
		form.password.data = ''
		form.password_again.data = ''
		flash("Passwords are not the same",'error')

	return render_template('register.html',
		g = g,
		form = form)






if __name__ == '__main__':
	app.debug = True
	app.run(host = 'localhost', port = 5000)