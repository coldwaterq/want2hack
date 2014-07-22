#! /usr/bin/python
from os import makedirs, path, walk, remove, rmdir, mkdir, chmod
from shutil import rmtree, copytree
from werkzeug import secure_filename
from flask import abort, g, make_response, request
from time import time
from subprocess import Popen, PIPE
import json
import stat as S
import traceback
import re
from werkzeug.exceptions import ImATeapot
import string
import glob
from codecs import open

class FileManager :
    app=None

    def __init__(self, app) :
        self.app = app
        print "FileManager initialized..."
    
    # challenge_id
    # name
    def make_file(self, foldername, filename, challenge_id):
        try:
            fi = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base/'+foldername
            if fi[-1]=='/':
                fi=fi[:-1]
            if(not path.normpath(fi) == fi and foldername != ''):
                return('Stop hacking me! ahum, I mean. There was an error making that file')
            if(not secure_filename(filename) == filename and not '.'+secure_filename(filename) == filename):
                return('Stop hacking me! ahum, I mean. There was an error making that file')
            if(foldername != '' and not path.exists(fi)):
                mkdir(fi)
            if(filename != ''):
                fi = path.normpath(fi)+'/'+filename
                open(fi,'w',encoding='utf-8').close()
            chmod(fi, S.S_IRWXU | S.S_IRWXG | S.S_IRWXO)
            return('The file has been made')
        except Exception, e:
            self.app.logger.warning('make_file '+str(e))
            return('There was an error making that file')        

    # challenge_id
    # name
    def remove_file(self, name_id, challenge_id):
        try:
            fi = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base'+self.get_files(challenge_id)[int(name_id)][0]
            if(not secure_filename(str(challenge_id)) == str(challenge_id)):
                return('the name is unsecure')
            try:
                remove(fi)
            except:
                rmdir(fi)
            return('The removal worked')
        except Exception, e:
            self.app.logger.warning('remove_file '+str(e))
            return('There was an error removing that file')


    # challenge_id needed to make the folder
    def create_challenge(self, challenge_id):
        # if the challenge id is at all controlled by the user,
        # it needs to be changed because file injection would
        # be possible
        makedirs(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base')

    # challenge_id is the challenges id
    # content is the contents of the file
    # name is the name of the file
    def update_file(self, name_id, content, challenge_id):
        fi = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base'+self.get_files(challenge_id)[int(name_id)][0]
        if( secure_filename(str(challenge_id)) == str(challenge_id)
            and secure_filename(name_id)==name_id):
            f = open(fi,'w',encoding='utf-8')
            f.write(content)
            f.close()

    # challenge_id need to get the files
    def get_files(self, challenge_id):
        fi = path.join(self.app.config['SERVER_ROOT'],'sand',str(challenge_id),'base')
        efiles = []
        for root, dirs, files in walk(fi):
            folder = root.partition(fi)[2]+'/'
            if(len(files) == 0 and len(dirs) == 0 and folder != '/'):
                efiles.append(folder)
            for file in files:
                efiles.append(path.join(folder,file))
        files = []
        for f in efiles:
            try:
                content = open(fi+f,encoding='utf-8').read()
            except:
                content=None
            files.append((f,content,efiles.index(f),content is not None))
        return files

    def get_approval_files(self, challenge_id):
        fi = path.join(self.app.config['SERVER_ROOT'],'sand',str(challenge_id),'base-approve')
        efiles = []
        for root, dirs, files in walk(fi):
            folder = root.partition(fi)[2]+'/'
            if(len(files) == 0 and len(dirs) == 0 and folder != '/'):
                efiles.append(folder)
            for file in files:
                efiles.append(path.join(folder,file))
        files = []
        for f in efiles:
            try:
                content = open(fi+f,encoding='utf-8').read()
            except:
                content=None
            files.append((f,content,efiles.index(f),content is not None))
        return files


    # requested file path
    # dict containing challenge information
    def serve_challenge_file(self, directory, challenge_id) :
        if directory is None:
            directory = 'index'
        attacker = str(g.user['user_id'])
        try:
            if(not path.exists(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker)):
                return(redirect('//'+self.app.config['SERVER_NAME']+'/challenge/checkout/'+str(challenge_id)))
            directory = directory.partition('?')[0]
            ftest = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker+'/'
            if( not path.normpath(ftest+directory)[:len(ftest)]==ftest):
                abort(418)

            if('/.' in path.normpath(ftest+directory)):
                return(make_response(self.app.config['CHALLENGE_PAGE_404']))

            if( not path.exists(ftest+directory) or directory[-1] == '/'):
                # to support the whole index thing
                if(directory == 'index' or directory[-1] == '/'):
                    d = directory.rpartition('/')[0]
                    if(path.exists(self.app.config['SERVER_ROOT']+'sand/'
                           +str(challenge_id)+'/'+attacker
                           +'/'+d+'/'+'index.php')):
                        directory = d+'/'+'index.php'
                    elif(path.exists(self.app.config['SERVER_ROOT']+'sand/'
                           +str(challenge_id)+'/'+attacker
                           +'/'+d+'/'+'index.py')):
                        directory = d+'/'+'index.py'
                    elif(path.exists(self.app.config['SERVER_ROOT']+'sand/'
                           +str(challenge_id)+'/'+attacker
                           +'/'+d+'/'+'index.html')):
                        directory = d+'/'+'index.html'
                    if(directory[0]=='/'):
                        directory = directory[1:]

            try:
                resp = self.make_response_challenge(attacker, challenge_id, directory)
            except Exception, e:
                if(self.app.config['DEBUG']):
                    self.app.logger.warning('serve_challenge_file1 '+str(e))
                try:
                    return(make_response(open(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker+'/'+directory,encoding='utf-8').read()))
                except:
                    return(make_response(self.app.config['CHALLENGE_PAGE_404']))
            return make_response(resp)        
        except ImATeapot, e:
            raise e
        except Exception, e:
            self.app.logger.warning('serve_challenge_file2 '+str(e))

    def addEnv(self, name, env):
        try:
            env[name] = str(request.environ[name])
        except:
            pass

    # was run_challenge_helper
    def make_response_challenge(self, attacker, challenge_id, directory):
        f = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker+'/'+directory
        length = int(request.environ.get('CONTENT_LENGTH', '0'))
        data = request.environ['wsgi.input'].read(length)
        envi = {'REDIRECT_STATUS':'true',
           'REQUEST_METHOD':request.method,
           'SCRIPT_FILENAME':f,
           'SCRIPT_NAME':directory.split('/')[-1],
           'PATH_INFO':'/',
           'SERVER_NAME':self.app.config['SERVER_NAME'],
           'SERVER_ADDR':self.app.config['SERVER_ADDR'],
           'REQUEST_TIME':str(int(time())),
           'REQUEST_TIME_FLOAT':str(time()),
           'DOCUMENT_ROOT':'/',
           'REMOTE_ADDR':request.remote_addr,
           'SERVER_ADMIN':'Secret',
           'PATH_TRANSLATED':f,
           'GATEWAY_INTERFACE':'CGI/1.1',
           'CONTENT_LENGTH':str(length),
           }
        self.addEnv('SERVER_PROTOCOL',envi)
        self.addEnv('REQUEST_URI',envi)
        self.addEnv('QUERY_STRING',envi)
        self.addEnv('PHP_AUTH_USER',envi)
        self.addEnv('PHP_AUTH_DIGEST',envi)
        self.addEnv('SERVER_SIGNATURE',envi)
        self.addEnv('SERVER_PORT',envi)
        self.addEnv('REDIRECT_REMOTE_USER',envi)
        self.addEnv('REMOTE_USER',envi)
        self.addEnv('REMOTE_PORT',envi)
        self.addEnv('REMOTE_HOST',envi)
        self.addEnv('PHP_AUTH_PW',envi)
        self.addEnv('AUTH_TYPE',envi)
        self.addEnv('CONTENT_TYPE',envi)
        for (key,value) in request.headers:
            if(key.upper() == 'COOKIE'):
                cookies = value.split(';')
                c = []
                for cookie in cookies:
                    if(self.app.config['SESSION_COOKIE_NAME'] not in cookie):
                        c.append(cookie)
                value = ';'.join(c)
            envi['HTTP_'+key.upper().replace('-','_')] = value
        if(self.app.config.get('SSL')):
            envi['HTTPS'] = 'yes'
        if(path.exists(f)):
            chmod(f, S.S_IRWXU | S.S_IRWXG | S.S_IRWXO)
            p = Popen([f],
                stdout=PIPE,
                stdin=PIPE,
                stderr=PIPE,
                env = envi,
                cwd=f.rpartition('/')[0]+'/')
            p.stdin.write(data)
            p.stdin.close()
            t = time()
            while(p.poll()==None):
                if(time()-t > self.app.config['CHALLENGE_TIMEOUT']):
                    p.kill()
                    return( "\n\n<h1>ERROR: This script ran to long, we killed it, "
                                 + "here is what was done thus far<h1>"
                                 + p.stdout.read())+'\n\n'+p.stderr.read()
            err =  p.stderr.read() 
            resp = p.stdout.read()
            if(err is not None and len(err) > 0):
                resp = resp+'\n'+err
        else:
            return(self.app.config['CHALLENGE_PAGE_404'], 404)
        resp = re.split('(\r\n\r\n|\n\n|\r\r)',resp)
        if(len(resp) == 1):
            response = make_response(resp[0])
        else:
            response = make_response(string.join(resp[2:],''))
            for header in re.split('(\r\n|\r|\n)',resp[0]):
                head = header.partition(':')
                if('STATUS' in head[0].upper()):
                    response.status = head[2].split()[0]
                elif(head[1] == ':'):
                    response.headers[head[0]] = head[2]
        return(response)

    def publish(self,challenge_id):
        try:
            rmtree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base-approve')
        except:
            pass
        copytree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base',
            self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base-approve')

    def approve(self,challenge_id):
        try:
            rmtree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base-published')
        except:
            pass
        copytree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base-approve',
            self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/base-published')

    def setup_challenge_sandbox(self, challenge_id, owner):
        attacker = str(g.user['user_id'])
        fi = self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker
        if(secure_filename(str(challenge_id)) == challenge_id):
            return(False)
        if(path.exists(fi)):
            rmtree(fi)
        try:
            copytree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+('/base' if owner else '/base-published'), fi)
            temp = open('.configs/challenge.aa',encoding='utf-8').read()
            temp = temp.replace('{SERVER_ROOT}',self.app.config['SERVER_ROOT'])
            temp = temp.replace('{CHALLENGE}',str(challenge_id))
            temp = temp.replace('{ATTACKER}',attacker)
            self.app.config['PRIV'].addAppArmorProfile(fi, temp)
            return(True)
        except Exception, e:
            rmtree(self.app.config['SERVER_ROOT']+'sand/'+str(challenge_id)+'/'+attacker)
            raise
        
