#! /usr/bin/python

############################################################################################
## This is all of the global configuration settings, basicly everything that nees to be 
## shared throughout the app is stored here
############################################################################################

import re, string, json
import collections
from werkzeug import secure_filename
import md5
import app_routes
import traceback
from flask_mail import Mail
import logging
import ConfigParser
from os import urandom

app = app_routes.app

# Hard Coded Configuration - these shoudl be gone at some point maybe
app.config['DIFFICULTY'] = ['Script Kiddy','Easy','Normal','Hard','1337']
app.config['SESSION_COOKIE_NAME'] = 'Vkd0R1RsSlJQVDA9'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['CHALLENGE_PAGE_404'] = '<html><h1>WTF</h1><p>This challenge does not have content for this page. You are either headed in the wrong direction or you need to do some guessing. If this is the first page of the challenge, then you definitely need to do some guessing.</p></html>'
app.config['FILE_REGEX'] = '^[a-zA-Z0-9.\-_]*$'
app.config['FOLDER_REGEX'] = '^[a-zA-Z0-9.\-_/]*$'
app.config['USERNAME_REGEX'] = '^[a-zA-Z0-9\-_!@$%^&*()+=|;:\'.,~`^ ]+$'
app.config['EMAIL_REGEX'] = '^[a-zA-Z0-9+_.\-]+@[a-zA-Z0-9+_.\-]+$'

# Configurable Configuration, use the configuration file
defaults = {'DEBUG':True,
    'SESSION_COOKIE_SECURE': True,
    'SERVER_ROOT':'Set This',
    'SERVER_NAME':'testing.test',
    'SERVER_ADDR':'127.0.0.1',
    'SERVER_UID':'1000',
    'SERVER_GID':'65535',
    'MAIL_SERVER':'smtp.gmail.com',
    'MAIL_PORT':'587',
    'MAIL_USE_TLS':True,
    'DB_PASSWORD':'Set This',
    'MAIL_USERNAME':'Set This',
    'MAIL_PASSWORD':'Set This',
    'MAIL_DEFAULT_SENDER_NAME':"Want2Hack",
    'ADMIN_USERS':[],
    'KEY_DIR':'/etc/ssl/certs',
    'CHALLENGE_TIMEOUT':'3',
    'LOGGING_TO_ADDR':'NoOne',
    'MAX_FILE_SIZE': '204800'
    }
conf = ConfigParser.SafeConfigParser(defaults)
conf.read('/etc/want2hack.conf')

# initialize some things if the DB_PASSWORD is 'Set This' since that
# should be one of the first things to be configured.
if( conf.get('DEFAULT','DB_PASSWORD') == 'Set This'):
    print('Either you choose the worst password for your database,\
        or you have yet to setup your config. You should be able to\
        edit the file /etc/want2hack.conf which I will now try to\
        create. I will also attempt to set up apparmor for you.')
    f = open('/etc/want2hack.conf','w')
    conf.write(f)
    f.close()

    raise RuntimeError('/etc/want2hack.conf not set. do it')

# Read in the configs into the app
def getvalue(option):
    try:
        return conf.getint('DEFAULT', option)
    except ValueError:
        pass
    try:
        return conf.getfloat('DEFAULT', option)
    except ValueError:
        pass
    try:
        return conf.getboolean('DEFAULT', option)
    except ValueError:
        pass
    return conf.get('DEFAULT', option, raw=True)

for name in defaults.keys():
    app.config[name] = getvalue( name )
app.config['ADMIN_USERS'] = eval(app.config['ADMIN_USERS'])
app.config['MAIL_DEFAULT_SENDER'] = (app.config['MAIL_DEFAULT_SENDER_NAME'],
    app.config['MAIL_USERNAME'])

# There shouldn't be any content length larger than 1Kb more than the max file size.
app.config['MAX_CONTENT_LENGTH'] = app.config['MAX_FILE_SIZE'] + 1024
    
# This catches all error messages on the server and logs them to the file erros.log
from logging.handlers import RotatingFileHandler
from logging.handlers import SMTPHandler
import logging

app.logger.setLevel(logging.DEBUG) # so the loggers work
if(not app.config['DEBUG']):
    app.logger.propagate = False

fhandler = RotatingFileHandler('/var/log/want2hack.log', mode='a', maxBytes=1048576, backupCount=5 )
fhandler.setLevel(logging.INFO)
format = logging.Formatter('%(asctime)s | %(message)s')
fhandler.setFormatter(format)
app.logger.addHandler(fhandler)
if(app.config['LOGGING_TO_ADDR'] != None and app.config['LOGGING_TO_ADDR'] != 'NoOne'):
    emailhandler = SMTPHandler((app.config['MAIL_SERVER'],app.config['MAIL_PORT']),
        app.config['MAIL_USERNAME'],
        [app.config['LOGGING_TO_ADDR']],
        'Want2Hacke Error',
        (app.config['MAIL_USERNAME'],app.config['MAIL_PASSWORD']),
        ())
    emailhandler.setLevel(logging.WARNING)
    app.logger.addHandler(emailhandler)

app.logger.info("The current root of the server is "+app.config['SERVER_ROOT'])
app.logger.info("SERVER_NAME: "+app.config['SERVER_NAME'])
app.url_map.default_subdomain =''

# The Mailer, because it was initialized before the settings otherwise
app.config['MAIL'] = Mail(app)
    
app.secret_key = urandom(24)
