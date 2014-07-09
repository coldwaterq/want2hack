#! /usr/bin/python

############################################################################################
## These are the routes, essentially it attaches methods to pages
## There are a few helper methods here to.
############################################################################################

from flask import *
from flask_mail import Message
from DatabaseManager import DatabaseManager
from FileManager import FileManager
from functools import wraps
from shutil import rmtree
import traceback
import re
from urllib import quote
import time

app = Flask("__main__") # This is not used correctly as of now.

# Database Manager
db_man = DatabaseManager(app)

# File Manager
file_man = FileManager(app)


# Base 36 encode/decode used in the subdomains
convert = ['0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']

# encode challenge_ids for use in subdomains, just makes them grow a bit slower
def encode(challenge_id):
	if challenge_id == 0:
		return('0')
	challenge_id36 = ''
	while challenge_id > 0:
		challenge_id36 = convert[challenge_id%36]+challenge_id36
		challenge_id = challenge_id / 36
	return challenge_id36

# decode the encoded challenge_ids
def decode(challenge_id36):
	challenge_id = 0
	for var in challenge_id36:
		challenge_id = challenge_id * 36
		challenge_id = challenge_id + convert.index(var)
	return challenge_id


################
## DECORATORS ##
################
# makes ssl be required
def require_ssl(fn) :
	@wraps(fn)
	def decor(*args, **kwargs) :
		if(request.url.startswith('https://')):
			return fn(*args, **kwargs)
		else:
			return redirect(request.url.replace('http://','https://'))
	return decor

# makes sure that a user is logged in, and that ssl is being used,
# since we use the secure flag on the session token, any page that
# requires user also requires ssl to function.
def require_user(fn) :
	@wraps(fn)
	@require_ssl
	def decor(*args, **kwargs) :
		if g.user is not None :
			return(fn(*args, **kwargs))
		else:
			return redirect('//'+app.config['SERVER_NAME']+'/user/signin')
	return decor

############
## Routes ##
############
# redirects to the static favicon.ico
@app.route('/favicon.ico')
def favicon():
	return(redirect('/static/favicon.ico'))

# our robots.txt
@app.route('/robots.txt')
def robots():
	return("User-agent: *\nDisallow:\n")

# The home page for unlogged in users
# if a user is logged in it redirects to dashboard
@app.route('/', methods=['GET','HEAD'])
@require_ssl
def home() :
	if g.user is not None:
		return redirect('/dashboard')
	leaders = db_man.get_leaders(num=10)
	return render_template('pages/index.html',leaders=leaders)# not logged in home page

# Our ssl certificate includes a-blog so should probably deal with it
# Currrently we just redirect to our blog page, and also a-blog will
# never be a challenge subdomain, they don't include -
@app.route('/',subdomain='a-blog')
def blog_subdoamin():
	return redirect('//'+app.config['SERVER_NAME'] + '/blog')

# The actual blog page, just returns a static page right now
@app.route('/blog')
def blog():
	return render_template('pages/blog.html')

# The about page, has an faq, and talks about the site a bit
# also just a static page, which I think works for it
@app.route('/about')
@require_ssl
def about() :
	return render_template('pages/about.html')

# The analytics page which is included on every
# page so that I know what people are doing on
# the site.
@app.route('/analytics')
def analytics():
	if g.user is None:
		username = None
	else:
		username = g.user['username']
	referer = request.referrer
	user_agent = request.headers.get('User-Agent')
	db_man.track(username=username, referer=referer, user_agent=user_agent)
	return make_response()

# A static page that contains our contact info
# only gives out the email if the user is logged in
@app.route('/contact')
@require_ssl
def contact():
	return render_template('pages/contact.html')

# Where users can see a list of all challenges, The template
# also contains a javascript function that allows the challenges
# to be searched and includes pagination
@app.route('/challenges')
@require_user
def challenges() :
	page = request.args.get('page', 0, type=int)
	count = request.args.get('count', 8, type=int)
	challenges = db_man.get_challenges(approved=True)
	try:
		challenges = challenges[page*count:(page+1)*count]
	except:
		challenges = challenges[:10]
	attacks_challenges = []
	attacks = db_man.get_attacks(user_id=g.user['user_id'])
	indexer = {}
	for attack in attacks:
		indexer[attack['challenge_id']] = attacks.index(attack)
	for challenge in challenges:
		try:
			index = indexer[challenge['challenge_id']]
			attacks_challenges.append((challenge, attacks[index]))
		except KeyError:
			attacks_challenges.append((challenge, None))
	return render_template('pages/challenges.html', attacks_challenges=attacks_challenges, page=page, count=count)

# The current scoreboard, shows the top 10 people, and the points they have
# Should this be like challenges, and show all the users, or should we keep
# it as just the top.
@app.route('/scoreboard')
@require_ssl
def scoreboard():
	page = request.args.get('page', 0, type=int)
	count = request.args.get('count', 8, type=int)
	leaders = db_man.get_leaders()
	try:
		leaders = leaders[page*count:(page+1)*count]
	except:
		leaders = leaders[:10]
	return render_template('pages/scoreboard.html', leaders=leaders, page=page, count=count)

# The hall of fame where we give credit for people that have done really cool things on the site.
# this needs the fancy tables like 
@require_ssl
@app.route('/hof')
def hof():
	page = request.args.get('page', 0, type=int)
	count = request.args.get('count', 8, type=int)
	hof = db_man.get_hall_of_fame()
	try:
		hof = hof[page*count:(page+1)*count]
	except:
		hof = hof[:10]
	return render_template('pages/hof.html', hof=hof, page=page, count=count)


# The challenge subdomains, it hands the content off to the user created content
# and checks if the user won
@app.route('/<path:url>', subdomain='<challenge_id36>', methods=['GET', 'POST'])
@app.route('/', subdomain='<challenge_id36>', methods=['GET', 'POST'])
@require_user
def challenge_router(challenge_id36, url=None) :
	try:
		challenge_id = decode(challenge_id36)
		challenge_attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id = challenge_id)[0]
	except:
		flash('The challenge was not checked out yet.')
		return redirect('//'+app.config['SERVER_NAME'] + '/dashboard')
	if challenge_attack is None :
		# challenge not checked out
		flash('The challenge was not checked out yet.')
		return redirect('//'+app.config['SERVER_NAME'] + '/dashboard/challenge/' + str(challenge_attack['challenge_id']))
	elif not challenge_attack['is_latest_version'] :
		# version is incorrect
		flash('You need to update this challenge to continue.')
		return redirect('//'+app.config['SERVER_NAME'] + '/dashboard/challenge/' + str(challenge_attack['challenge_id']))
	# before returning the file, check if win page?
	resp = file_man.serve_challenge_file(directory = url, challenge_id = challenge_attack['challenge_id'])
	t = time.time()
	if(challenge_attack['flag_seed'] in resp.data):
		if(challenge_attack['owner_id']==g.user['user_id']):
			flash('It worked! but since you made it, you don\'t get points')
			return(redirect('//'+app.config['SERVER_NAME']+'/dashboard'))
		elif challenge_attack['complete']:
			flash('You have already beaten this challenge, so you don\'t get any more points')
			return(redirect('//'+app.config['SERVER_NAME']+'/dashboard'))
		else:
			if(db_man.win(challenge_id=challenge_id)):
				flash('Congrats, you beat that challenge and shall recieve points')
			else:
				flash('Go home '+app.config['SERVER_NAME']+', your drunk. Report this bug that kept you from getting points')
		return(redirect('//'+app.config['SERVER_NAME']+'/challenge/finish/'+str(challenge_id)))
	delta = 0.002
	if(time.time()-t > delta):
		app.logger.warning('time to check win was '+str(time.time()-t)+' to protect against constant time comparison the current limit of '+str(delta)+' should be increased')
	while(time.time()-t < delta):
		time.sleep(delta/10)
	return resp

# The landing page to help keep people from beeing stupid
@app.route('/challenge/landing/<int:challenge_id>')
@require_user
def challenge_landing(challenge_id):
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)[0]
	except:
		flash('Something didn\'t work')
		return redirect('/dashboard')
	if attack['complete']:
		flash('You have completed this challenge already')
		return redirect('/dashboard')
	encoded_challenge_id = encode(challenge_id)
	challenge_location='//'+encoded_challenge_id+'.'+app.config['SERVER_NAME']+'/'
	return render_template('pages/landing.html',challenge_location=challenge_location)

# Adds the challenge to the logged in users list of attacks
@app.route('/challenge/checkout/<int:challenge_id>')
@require_user
def challenge_checkout(challenge_id) :
	# I think this should the URL in which it adds a challenge to the user's attack list.
	if len(db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)) != 0:
		flash('You have already checked out this challenge')
		return redirect('/dashboard/challenge/'+str(challenge_id))

	challenge = db_man.get_challenge(challenge_id = challenge_id)
	try:
		owner=challenge['owner_id']==g.user['user_id']
	except:
		return(abort(418))
	if(not owner and challenge['latest_published_version'] is None):#The challenge should be None if it isn't published, real, or not allowed for some reason
		return(abort(418))
	if owner:
		version = challenge['latest_version']
	else:
		version = challenge['latest_published_version']
	if(not file_man.setup_challenge_sandbox(challenge_id = challenge['challenge_id'], owner=owner)):
		flash("the challenge failed to be checked out")
	elif(db_man.checkout_challenge(user_id=g.user['user_id'], challenge_id=challenge_id,version=version)):
		flash('you have checked out the challenge')
		return redirect('/dashboard/challenge/'+str(challenge_id))
	else:
		flash('the challange failed to be checked out')
	return redirect('/dashboard')

# Reset all the files, and reload the apparmor profile for good measure.
# the main reason to keep the apparmor profile reload, is that I ocasionlly
# have to make changes to the profiles, and I can just tell users to hit
# restart to fis their problems.
@app.route('/challenge/restart/<int:challenge_id>')
@require_user
def challenge_restart(challenge_id) :
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)[0]
	except:
		flash('Something didn\'t work')
		return redirect('/dashboard')
	if(attack['complete']):
		flash('You have allready completed this challenge, you have no need to resatart it')
		return redirect('/dashboard')
	challenge=db_man.get_challenge(challenge_id=challenge_id)
	file_man.setup_challenge_sandbox(challenge_id = challenge_id, owner=challenge['owner_id']==g.user['user_id'])
	flash('challenge reset')
	return redirect('/dashboard/challenge/'+str(challenge_id))

# Tells the user they won and also asks for a difficulty rating of the challenge
@app.route('/challenge/finish/<int:challenge_id>', methods=['GET','POST'])
@require_user
def challenge_finish(challenge_id) :
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)[0]
	except:
		flash('Something didn\'t work')
		return redirect('/dashboard')
	if attack['voted_difficulty'] is not None:
		flash('You have alread voted on this challenge, you don\'t get to vote again')
		return redirect('/dashboard')
	elif not attack['complete']:
		flash('You have not finished the challenge though')
		return redirect('/dashboard')
	if(request.method=="POST"):
		rating = int(request.form['rating'])
		if(rating < 1 or rating > 5):
			abort(418)
		db_man.user_rating(rating=rating, challenge_id=challenge_id)
		return(redirect('/dashboard'))
	return render_template('pages/finish.html',difficulty=attack['user_points_received']/10)
	
# The main page, From here users can attack, create, give up, and find new challenges
# This is the home page for logged in users
@app.route('/dashboard')
@require_user
def dashboard():
	challenges = db_man.get_challenges(user_id=g.user['user_id'])
	attacked_challenges = db_man.get_attacks(user_id=g.user['user_id'])
	return render_template('pages/dashboard.html', challenges=challenges, attacked=attacked_challenges)

# Shows information about a challenge
@app.route('/dashboard/challenge/<int:challenge_id>/profile')
@require_user
def challenge_profile(challenge_id):
	challenge = db_man.get_challenge(challenge_id=challenge_id)
	if(challenge is None):
		flash('That is not something you are allowed to do.')
		return(redirect('/dashboard'))
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'], challenge_id=challenge_id)[0]
	except:
		attack = None
	try:
		if challenge['owner_id']!=g.user['user_id'] and challenge['latest_published_version'] is None:
			flash('That is not something you are allowed to do.')
			return redirect('/dashboard')	
		attackers = db_man.get_attackers(challenge_id=challenge_id)		
		return render_template('pages/challenge.html', challenge=challenge, attack=attack, attackers=attackers)
	except Exception, e:
		app.logger.warning('challenge_profile '+str(e))
		flash('That is not something you are allowed to do.')
		return redirect('/dashboard')

# If you are the owner of the challenge, you can edit it
# if you are not you see a challenge profile for the challenge
@app.route('/dashboard/challenge/<int:challenge_id>', methods=['POST','GET']) # overview of files and directorys of challenge
@require_user
def singal_challenge(challenge_id):
	challenge = db_man.get_challenge(challenge_id=challenge_id)
	if(challenge is None):
		flash('That is not something you are allowed to do.')
		return(abort(418))
	try:
		if challenge['owner_id']!=g.user['user_id'] :
			return redirect('/dashboard/challenge/'+str(challenge_id)+'/profile')
	except Exception, e:
		app.logger.warning('singal_challenge '+str(e))
		flash('That is not something you are allowed to do.')
		return redirect('/dashboard')

	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'], challenge_id=challenge_id)[0]
	except:
		attack = None

	difficulty_estimate = db_man.get_difficulty_estimate(challenge_id=challenge_id, version=challenge['latest_version'])[0]
	if(request.method == "POST"):
		publish = request.form.get('publish')
		if publish is not None:
			if(db_man.publish(challenge_id=challenge_id, latest_version=challenge['latest_version'], difficulty_estimate=difficulty_estimate)):
				file_man.publish(challenge_id=challenge_id)
				flash('The challenge has been submitted for approval, you are now working on the new one.')
				msg = Message("Challenge Awaiting Approval")
				msg.recipients = []
				for user in app.config['ADMIN_USERS']:
					email = db_man.get_user(username=user)['email']
					msg.recipients.append(email)
				msg.html =  '''
							A challenge is awaiting approval on %s.
							''' % (app.config['SERVER_NAME'])
				try:
					app.config['MAIL'].send(msg)
				except Exception, e:
					app.logger.warning('The "challenge is awaiting approval" message was not sent because off ' + str(e))

		else:
			name = request.form['name']
			difficulty=int(request.form['difficulty'])
			description = request.form['description']
			if(re.match(app.config['USERNAME_REGEX'], name) is None or difficulty < 1 or difficulty > 5):
				flash('Those inputs were invalid, '+app.config['USERNAME_REGEX']+' is allowed')
				return redirect('/dashboard/challenge/'+str(challenge_id))
			success = db_man.update_challenge(challenge_id=challenge_id, name=name, difficulty=difficulty, version=challenge['latest_version'], description=description)
			if(success):
				flash('The settings have been changed')
			else:
				flash('There was an error in saving the settings')
		return redirect('/dashboard/challenge/'+str(challenge_id))
	if challenge is not None:
		files = file_man.get_files(challenge_id)
		if files is None:
			return(abort(418))
		difficulty_estimate = db_man.get_difficulty_estimate(challenge_id=challenge_id, version=challenge['latest_version'])[0]
		return render_template('pages/edit.html',challenge=challenge, files=files, attack=attack, difficulty=difficulty_estimate)
	return redirect('/dashboard')

# Adds a file to the challenge
@app.route('/dashboard/challenge/add_file/<int:challenge_id>', methods=['POST'])# POST only => re:dashboard
@require_user
def add_file(challenge_id):
	try:
		if db_man.get_challenge(challenge_id=challenge_id)['owner_id']!=g.user['user_id']:
			raise Exception
	except:
		flash('That is not something you are allowed to do.')
		return abort(418)
	foldername=request.form['foldername']
	filename=request.form['filename']
        if(re.match(app.config['FILE_REGEX'], filename) is None and filename is not None):
		flash('The file name is invalid, '+app.config['FILE_REGEX']+' is allowed')
		return redirect('/dashboard/challenge/'+str(challenge_id))
	if(re.match(app.config['FOLDER_REGEX'], foldername) is None and foldername is not None) :
		flash('The folder name is invalid, '+app.config['FOLDER_REGEX']+' is allowed')
		return redirect('/dashboard/challenge/'+str(challenge_id))
	flash(file_man.make_file(foldername, filename, challenge_id))
	return redirect('/dashboard/challenge/'+str(challenge_id))

# removes the file from the challenge
@app.route('/dashboard/challenge/remove_file/<int:challenge_id>', methods=['POST'])# POST only => re:dashboard
@require_user
def remove_file(challenge_id):
	try:
		if db_man.get_challenge(challenge_id=challenge_id)['owner_id']!=g.user['user_id']:
			raise Exception
	except:
		flash('That is not something you are allowed to do.')
		return abort(418)
	name_id=request.form['name_id']
	flash(file_man.remove_file(name_id, challenge_id))
	return redirect('/dashboard/challenge/'+str(challenge_id))

# updates the contents of the challenge
@app.route('/dashboard/challenge/update_file/<int:challenge_id>', methods=['POST'])# POST only => re:dashboard
@require_user
def update_file(challenge_id):
	try:
		if db_man.get_challenge(challenge_id=challenge_id)['owner_id']!=g.user['user_id']:
			raise Exception
	except:
		flash('That is not something you are allowed to do.')
		return abort(418)
	content = request.form["content"]
	name_id = request.form["name_id"]
	file_man.update_file(name_id, content, challenge_id)
	return make_response(g.csrf)

# deletes the challenge, keeping the files, but not allowing anyone to
# work on it anymore
@app.route('/dashboard/challenge/delete', methods=['POST'])
@require_user
def delete_challenge():
	challenge_id = request.form['challenge_id']
	try:
		if db_man.get_challenge(challenge_id=challenge_id)['owner_id']!=g.user['user_id']:
			raise Exception
	except:
		flash('That is not something you are allowed to do.')
		return abort(418)
	worked = db_man.delete_challenge(challenge_id=challenge_id)
	if(worked):
		flash('that challenge has been deleted')
		return(redirect('/'))
	flash('An error occured trying to delete challenge')
	return(redirect('/'))

# Create a new challenge, creates the folders and all that
@app.route('/dashboard/challenge/new', methods=["POST"])
@require_user
def new_challenge():
	name = request.form['name']
	if(re.match(app.config['USERNAME_REGEX'], name) is None ):
		flash('That name is invalid, '+app.config['USERNAME_REGEX']+' is allowed')
		return redirect('/dashboard')
	if(len(name)>20):
		flash('There is a maximum length of 20 for the name')
		return redirect('/dashboard')
	challenge_id = db_man.new_challenge(challenge_name=name)
	try:
		file_man.create_challenge(challenge_id)
		flash('Your challenge has been created')
	except Exception, e:
		app.logger.warning(e)
		flash('There was an error creating that challenge')
	return redirect('/dashboard')

# DASHBOARD (ATTACKER MANAGEMENT)
# update the challenge, this is the only option when a challenge has been updated.
@app.route('/dashboard/attack/update/<int:challenge_id>')
@require_user
def update(challenge_id):
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)[0]
	except:
		flash('Something didn\'t work')
		return redirect('/dashboard')
	if attack['complete']:
		flash('You have already finished this challenge')
		return redirect('/dashboard')
	try:
		challenge=db_man.get_challenge(challenge_id=challenge_id)
		file_man.setup_challenge_sandbox(challenge_id=challenge_id,owner=challenge['owner_id']==g.user['user_id'])
		if(challenge['owner_id']==g.user['user_id']):
			version=challenge['latest_version']
		else:
			version=challenge['latest_published_version']
		db_man.update(challenge_id=challenge_id,version=version)
		flash('update worked')
		return redirect('/dashboard/challenge/'+str(challenge_id))
	except Exception, e:
		app.logger.error('update '+str(e))
		flash('Update failed')
	return redirect('/dashboard')

# give up a challenge
@app.route('/dashboard/attack/forfeit/<int:challenge_id>')
@require_user
def forfeit(challenge_id):
	try:
		attack = db_man.get_attacks(user_id=g.user['user_id'],challenge_id=challenge_id)[0]
	except:
		flash('Something didn\'t work')
		return redirect('/dashboard')
	if attack['complete']:
		flash('You have beaten this challenge so you can\'t forfeit, why would you want to give up earned points :)')
		return redirect('/dashboard')
	if db_man.forfeit_challenge(challenge_id=challenge_id):
		flash('You have addmitted defeat honorably')
	else:
		flash('There was an error givving up, maybe this is a sign from the gods.')
	return(redirect('/dashboard'))
#/dashboard/attack/notes

# USER
# user profiles, if no user is specified it shows your own
@app.route('/user')
@app.route('/user/<user>')
@require_user
def user_profile(user=None) :
	if user is None:
		return render_template('pages/user_settings.html')
	
	user_prof = db_man.get_user(username = user)
	if(user_prof is None):
		flash('That is not something you are allowed to do.')
		return(abort(418))

	attacks = db_man.get_attacks(user_id=user_prof['user_id'], completed=True)
	challenges = db_man.get_challenges(user_id=user_prof['user_id'], approved=True)

	if user_prof is None :
		return abort(404)

	return render_template('pages/user_profile.html', user_prof = user_prof, attacks=attacks, challenges=challenges)

# the sign in page
@app.route('/user/signin', methods=['GET', 'POST'])
@require_ssl
def user_signin() :
	if request.method == 'GET' :
		return render_template('pages/user_signin.html')
	else :
		username = request.form['username']
		password = request.form['password']

		user = db_man.user_signin(username = username, password = password)

		if user is not None :
			session['infsek_user'] = user['session_token']
			flash('You have successfully signed in')
			return redirect('/')
		else :
			flash('Sign in failed')
			return redirect('/user/signin')

# The signup page
@app.route('/user/signup', methods=['POST','GET'])
@require_ssl
def user_signup() :
	if request.method == 'GET' :
		return render_template('pages/user_signup.html')
	else :
		if request.form['email'] is None or request.form['email'] == '':
			flash('Please provide and email address to confirm your account')
			return redirect('/user/signup')
		elif 'mailinator.com' in request.form['email']:
			flash("I'm sorry, but mailinator never seems to work, you could use one of their alternate domains if you want though.")
			return redirect('/user/signup')
		elif re.match(app.config['USERNAME_REGEX'],request.form['username']) is None :
			flash('Your username are invalid, '+app.config['USERNAME_REGEX']+' is allowed')
			return redirect('/user/signup') 
		elif re.match(app.config['EMAIL_REGEX'],request.form['email']) is None:
			flash('Your email is invalid, '+app.config['EMAIL_REGEX']+' is allowed')
			return redirect('/user/signup')
		elif len(request.form['username']) > 34:
			flash('Your username can only be 34 characters long')
			return redirect('/user/signup')
		elif len(request.form['email']) > 64:
			flash('Congradulations, you have an incredibly long email. In fact I think it is too long')
			return redirect('/user/signup')
		else :
			try :
				usr = request.form['username']
				email = request.form['email']

				# get the confirmation key and replace problamatic characters
				# it is base64 so everything else should be letters and numbers
				conf_key = db_man.genkey(64)
				user = db_man.user_signup(username=usr, email=email, conf_key=conf_key)
				if user is not None :
					conf_key = user['conf_key'].replace('$','_').replace('.','-').replace('/','[').replace('+',']')
					msg = Message("Welcome to want2hack.com")
					msg.recipients = [email]
					msg.html =  '''
								<h3>welcome to the community</h3>
								<p>
									To confirm your account, please follow the link below.<br />
									<a href="https://%s/user/confirm/%s/%s">%s/user/confirm/%s/%s</a>.
								</p>
								''' % (app.config['SERVER_NAME'],usr,conf_key,app.config['SERVER_NAME'],usr,conf_key)
					try:
						app.config['MAIL'].send(msg)
					except Exception, e:
						app.logger.error('signup '+str(e))
					flash('Account successfully created. Please check your email for confirmation instructions. It may be in spam.')
					if(app.config['DEBUG']):
						print conf_key+' '+usr
				else :
					flash('There was an issue creating your account, try a different username')
					return redirect('/user/signup')
			except Exception, e:
				# TODO: check for unique column error, not general
				app.logger.critical('signup problem'+str(e))
				flash('Something went wrong, it has been reported')
			
			return redirect('/')
			
# the Signout page
@app.route('/user/signout')
@require_user
def user_signout() :
	db_man.user_signout(sesh = session['infsek_user'])
	session['infsek_user'] = None
	return redirect('/')

# password reset
@app.route('/user/reset', methods=['GET','POST'])
@require_ssl
def reset() :
	if(request.method == 'GET'):
		return render_template('pages/password_reset.html')
	conf_key = db_man.genkey(64)
	username = request.form['username']
	user = db_man.password_reset(username=username, conf_key=conf_key)
	if(user is None):
		flash('If that account existed, a password reset email was sent to it.')
		return redirect('/user/signout')
	email = user['email']
	conf_key = user['conf_key'].replace('$','_').replace('.','-').replace('/','[').replace('+',']')
	msg = Message("Password Reset for want2hack")
	msg.recipients = [email]
	msg.html =  '''
				<p>
					Please follow the link bellow to sign in and change your password<br />
					<a href="https://%s/user/confirm/%s/%s">%s/user/confirm/%s/%s</a>.
				</p>
				''' % (app.config['SERVER_NAME'],username,conf_key,app.config['SERVER_NAME'],username,conf_key)
	try:
		app.config['MAIL'].send(msg)
	except Exception, e:
		app.logger.error('send reset'+str(e))
	if(app.config['DEBUG']):
		print conf_key+' '+username
	if(g.user is not None):
		flash('You should recieve a reset email shortly, it may be in spam.')
	else:
		flash('If that account existed, a password reset email was sent to it. It may be in spam.')
	return redirect('/dashboard')

# User confirmation
@app.route('/user/confirm/<user>/<confirmation>', methods=['GET','POST'])
@require_ssl
def user_confirm(user,confirmation) :
	if(request.method == 'GET'):
		return render_template('pages/set_password.html')

	if(request.form['password1'] != request.form['password2']):
		flash('Those passwords don\'t match')
		return render_template('pages/set_password.html')

	if(request.form['password1'] == ''):
		password = None
	else:
		password = request.form['password1']

	confirmation = confirmation.replace('_','$').replace('-','.').replace('[','/').replace(']','+')
	user = db_man.user_signin(username = user, confirmation = confirmation, password=password)
	if user is not None:
		session['infsek_user'] = user['session_token']
		flash('You have succesfully signed in and set your password.')
	else :
		flash('There was a problem with that confirmation code, username combination. Try reseting your password again.')
	return redirect('/')

#####################
## Admin Functions ##
#####################

# The admin page, this shows the challenges that need to be approved
@app.route('/admin')
@require_user
def admin():
	if(g.user['username'] not in app.config['ADMIN_USERS']):
		abort(404)
	approvals = db_man.challenges_needing_approval()
	analytics = db_man.check_analytics(limit=100)
	return render_template('pages/admin.html', approvals=approvals, analytics=analytics)

@app.route('/admin/addhof', methods=['GET','POST'])
@require_user
def add_hof():
	if(g.user['username'] not in app.config['ADMIN_USERS']):
		abort(404)
	description = request.form['description']
	user_id = int(request.form['user_id'])
        if(user_id < 0):
            return
	points = int(request.form['points'])
	if db_man.add_hall_of_fame(user_id=user_id, description=description, points=points):
		flash('Hall of fame added')
	else:
		flash('That didn\'t work, maybe they got points for this already?')
	return redirect('/admin')

# Review of a challenge to be approved
@app.route('/approve/<challenge_id>', methods=['GET','POST'])
@require_user
def approve(challenge_id):
	if(g.user['username'] not in app.config['ADMIN_USERS']):
		abort(404)
	if request.method == 'GET':
		files = file_man.get_approval_files(challenge_id)
		challenge = db_man.get_challenge(challenge_id=challenge_id, admin=True)
		if challenge is None:
			abort(404)
		return render_template('pages/approve.html',files=files,challenge=challenge)
	elif request.method == 'POST' and db_man.approve(challenge_id=challenge_id):
		challenge = db_man.get_challenge(challenge_id=challenge_id, admin=True)
		reason = request.form.get('reason')
		msg = Message("Challenge Approved")
		msg.recipients = [ db_man.get_user(user_id=challenge['owner_id'])['email'] ]
		msg.html =  '''
					Your challenge on %s has been approved. This is the reason:\n
					%s\n
					Thank you,\n
					\n
					%s
					''' % (app.config['SERVER_NAME'], reason, app.config['SERVER_NAME']+' Team')
		try:
			app.config['MAIL'].send(msg)
		except Exception, e:
			app.logger.warning('The "challenge is awaiting approval" message was not sent because off ' + str(e))

		file_man.approve(challenge_id=challenge_id)
		flash('That challenge has been approved')
	else:
		flash('There was a problem approving that challenge. Please report it')
	return redirect('/admin')

# How a challenge is denied approval if need be
@app.route('/deny/<challenge_id>', methods=['POST'])
def deny(challenge_id):
	if(g.user['username'] not in app.config['ADMIN_USERS']):
		abort(404)
	if request.method == 'POST' and db_man.approve(challenge_id=challenge_id, approve=False):
		challenge = db_man.get_challenge(challenge_id=challenge_id, admin=True)
		reason = request.form.get('reason')
		msg = Message("Challenge not approved")
		msg.recipients = [ db_man.get_user(user_id=challenge['owner_id'])['email'] ]
		msg.html =  '''
					Your challenge on %s has been denied approval. This is the reason:\n
					%s\n
					\n
					If you can fix this issue and resubmit your challenge for approval it will be considered again.\n
					\n
					Thank you,\n
					\n
					%s
					''' % (app.config['SERVER_NAME'], reason, app.config['SERVER_NAME']+' Team')
		try:
			app.config['MAIL'].send(msg)
		except Exception, e:
			app.logger.warning('The "challenge is awaiting approval" message was not sent because off ' + str(e))

		flash('That challenge has been denied')
	else:
		flash('There was a problem denying that challenge. Please report it')
	return redirect('/admin')	


###################################
# Error Handlers
###################################
# handles 403 errors
@app.errorhandler(403)
def access_denied(e):
	return render_template('errors/403.html'), 403

# handles 404 errors
@app.errorhandler(404)
def page_not_found(e):
	return render_template('errors/404.html'), 404

# handles 418 errors
# I want people to get points the first time they find this,
# I just don't know if it should go in the hof, or as its
# own challenge that is challenge id -1 or something
@app.errorhandler(418)
def I_am_a_teapot(e):
	if(g.user is None):
		flash('I don\'t know how you got this without being logged in but please report it. You will be non-monitarilly rewarded.')
	else:
		if(db_man.add_hall_of_fame(user_id=g.user['user_id'], description='You found the mithical teapot', points=4)):
			flash('Congrats, you found the teapot, and recieved some points')
		else:
			flash('You keep finding the teapot')
	return render_template('errors/418.html'), 418

# handle 500 errors and ask the user to report them.
@app.errorhandler(500)
def server_error(e):
	return render_template('errors/500.html'), 500


###################################
# General request decorators
###################################
# The before request method, this also handles csrf
@app.before_request
def before_request() :
	# Just realized Flask may not scale well...
	g.conn = db_man.connect_db()
	try :
		g.user = db_man.get_user(sesh=session['infsek_user'])
	except KeyError, e :
		g.user = None
	if(request.method!='GET' and request.host==app.config['SERVER_NAME']):
		try:
			token = session['_csrf_token']
		except:
			flash('There was a problem with your session state, it should be resolved now.')
			return redirect('/')
		session['_csrf_token'] = None
		if not token or token != request.form.get('_csrf_token'):
			flash('You were just protected from CSRF, if this was in ERROR, Sorry.')
			abort(403)
	try:
		if(session['_csrf_token'] is None):
			session['_csrf_token'] = db_man.genkey(213)
		g.csrf = session['_csrf_token']
	except:
		session['_csrf_token'] = db_man.genkey(213)
		g.csrf = session['_csrf_token']

# in case something breaks
@app.teardown_request
def teardown_request(exception) :
	# In case of breakage
	g.conn.close()

# clean up if it all works.
@app.after_request
def record(response):
	try:
		g.conn.close()
		app.logger.info(request.remote_addr+' | '+str(response.status_code)+' | '+request.url)
	except Exception, e:
		app.logger.error('request logging'+str(e))
	return(response)
