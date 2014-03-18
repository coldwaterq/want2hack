from os import setuid, setgid
from multiprocessing import Process, Queue, Pipe
import subprocess
import traceback

#######################################################
# This is where you actually write the functions that
# are called by all the other people

# tests what user the subprocess is running as
def testUID():
    return runFunc(returnUID,())

def addAppArmorProfile(name, contents):
    ret = runFunc(rootAppArmorAdder, (name, contents))
    if( ret == '0'):
        return(True)
    else:
        raise Exception(ret)

# starts the subprocess as the current user and then
# drops the main script to the specified uid
def starty(uid,gid):
    global q
    global parent_conn
    global proc
    q = Queue()
    parent_conn, child_conn = Pipe()
    proc = Process(target=f, args=(q,child_conn,))
    proc.start()
    setgid(gid)
    setuid(uid)

# stops the subprocess, the main function will
# still be the lower level.
def stop():
    q.put(("stop",()))


#######################################################
# functions in this area require a special format to
# work. The parameters must be in two parameters like
# so.
# def test((name, age)):
#     print name
#
# or for a function with no arguments
# def test(none):
#     print "don't use none anywhere it will be ()"
#
# nothing bellow this should be called from outside
# this script, it won't work correctly
def rootAppArmorAdder((name, contents)):
    fi = '/etc/apparmor.d/'+name.replace('/','.')[1:]
    f = open(fi, 'w')
    f.write(contents)
    f.close()     
    s = subprocess.Popen(['apparmor_parser','-a', fi], stderr=subprocess.PIPE)
    ret = s.wait()
    if( ret != 0):
        s = subprocess.Popen(['apparmor_parser','-r',fi], stderr=subprocess.PIPE )
        ret = s.wait()
        out = s.stderr.read()
        if( ret != 0):
            return(out)
    return str(ret)

def returnUID(none):
    from os import getuid
    return(getuid())

#######################################################
# everything bellow here is what makes it work. Only
# change it if you have to
def f(q,conn):
    cmd = ""
    while(cmd != 'stop'):
        (cmd,params) = q.get()
        try:
            conn.send(cmd(params))
        except Exception, e:
            conn.send(str(e))
    conn.close()

def start(uid):
    global q
    global parent_conn
    global proc
    q = Queue()
    parent_conn, child_conn = Pipe()
    proc = Process(target=f, args=(q,child_conn,))
    proc.start()
    setuid(uid)

def stop():
    q.put(("stop",()))

def runFunc(f, parameters):
    q.put((f, parameters))
    return(parent_conn.recv())

def test((name,age)):
    return(name+' '+str(age))


if __name__ == '__main__':
    from os import getuid
    start(uid=1000)
    print testUID()
    print(getuid())
    for c in runFunc(test, ('name',4)):
        print str(ord(c))+' '+c
    print runFunc(rootAppArmorAdder, ('test','tse'))==1
    stop()
    # don't ever call proc.join ()unless you know what you
    # are doing, I just wanted to test that stop was
    # really working
    proc.join()
