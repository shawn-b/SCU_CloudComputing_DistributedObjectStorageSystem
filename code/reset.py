#!/usr/bin/python2.7

import os
import sys
import subprocess

# FIXME: Change this to your own username
USERNAME = 'username'

MY_TMP_PATH = '/tmp/' + USERNAME + '/'
CURRENT_USR = os.environ['USER']
SERVER_IPS = ['129.210.16.80', '129.210.16.83', '129.210.16.90', '129.210.16.93']

print('Removing directories from server machines...')

for diskIP in SERVER_IPS:
    print('Disk: ' + diskIP)
    rmCmd = 'ssh ' + CURRENT_USR + '@' + diskIP + ' rm -r ' + MY_TMP_PATH
    #subprocess.check_output(rmCmd, shell=True)
    os.system(rmCmd)

print('Removal process complete.')