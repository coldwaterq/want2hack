#! /usr/bin/python

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import tornado
import os
from app_config import app
import drop_privileges as priv

app.config["SSL"] = True

class ChangeServer(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        def custom_start_response(status, headers, exc_info=None):
            headers.append(('Server', "run for you lives!"))
            headers.append(('X-Frame-Options','DENY'))
            headers.append(('Strict-Transport-Security','max-age=31337031337'))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)

sockets = tornado.netutil.bind_sockets(443, address="0.0.0.0")

priv.starty(app.config['SERVER_UID'],app.config['SERVER_GID'])
app.config['PRIV']=priv

tornado.process.fork_processes(0)
server = HTTPServer(WSGIContainer(ChangeServer(app)), ssl_options={
    "certfile": os.path.join(app.config['KEY_DIR'], "want2hack.crt"),
    "keyfile": os.path.join(app.config['KEY_DIR'], "want2hack.key"),
})
server.add_sockets(sockets)
IOLoop.instance().start()
