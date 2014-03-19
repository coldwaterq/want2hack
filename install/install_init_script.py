#!/usr/bin/python

import ConfigParser
import os

conf = ConfigParser.SafeConfigParser()
conf.read('/etc/want2hack.conf')

temp = open('init.examp').read()
temp = temp.replace('{SERVER_ROOT}',conf.get('DEFAULT','SERVER_ROOT'))
f = open('/etc/init.d/want2hack', 'w')
f.write(temp)
f.close()

os.chmod('/etc/init.d/want2hack', 700)