#! /usr/bin/python

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import tornado
import os
from app_config import app
import drop_privileges as priv

class ChangeServer(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        def custom_start_response(status, headers, exc_info=None):
            headers.append(('Server', "<marquee>Run for your lives!!!</marquee>"))
            headers.append(('X-Frame-Options','DENY'))
            headers.append(('Strict-Transport-Security','max-age=31337031337'))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)

socket = tornado.netutil.bind_sockets(80, address="0.0.0.0")
secSocket = tornado.netutil.bind_sockets(443, address="0.0.0.0")

priv.starty(app.config['SERVER_UID'],app.config['SERVER_GID'])
app.config['PRIV']=priv

# setup apparmor when the server is started if it hasn't been already
if (app.config['SERVER_ROOT'] != 'Set This'):
    try:
        open('../LICENSE')
        print 'apparmor isn\'t set up so I will try that now for the server'
        temp = open('.configs/app.aa').read()
        temp = temp.replace('{SERVER_ROOT}',app.config['SERVER_ROOT'])
        app.config['PRIV'].addAppArmorProfile(app.config['SERVER_ROOT'][0:]+'app', temp)
        print 'done'
    except:
    	pass

tornado.process.fork_processes(0)
server = HTTPServer(WSGIContainer(ChangeServer(app)))
secServer = HTTPServer(WSGIContainer(ChangeServer(app)), ssl_options={
    "certfile": os.path.join(app.config['KEY_DIR'], "want2hack.crt"),
    "keyfile": os.path.join(app.config['KEY_DIR'], "want2hack.key"),
    "ciphers":"HIGH", # I want this to be diffie hellman, but haven't gotten it to work yet.
})
server.add_sockets(socket)
secServer.add_sockets(secSocket)

IOLoop.instance().start()
