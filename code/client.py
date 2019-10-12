#!/usr/bin/python2.7

###########################################################
#
# File:     client.py
#
# Desc:     A basic stream socket client program in which 
#           a client user can issue various commands to be
#           processed and executed by a storage server program
#           where user can store/retrive/manage objects.
# 
#           Once a TCP socket connection has been established
#           with the server, the client runs indefinitely in a 
#           terminal-like user interface. The commands allow
#           for the uploading, downloading, deleting, and
#           listing of objects that belong to a particular
#           user.
#           
# Author:   Shawn Bhagat
# Class:    COEN241 Cloud Computing
# 
###########################################################

###########################################################
# IMPORT NEEDED MODULES
###########################################################

import sys
import socket
import os
import subprocess

###########################################################
# DEFINE GLOBAL VARIABLES AND CONSTANTS
###########################################################

# Get server machine name/IP and listening port from command line args
if len(sys.argv) != 3:
    print('USAGE: client [host-name|host-IP-address] [port]')
    sys.exit(1)
else:
    HOST = str(sys.argv[1]) # server machine name or IP address
    PORT = int(sys.argv[2]) # port on which server machine is listening for client connections

# Socket variables
BUFFER_SIZE = 4096  # max buffer size for data transmission between client & server

# List of valid command names that can be run in client terminal UI
VALID_CMDS = ['upload', 'download', 'delete', 'list', 'add', 'remove', 'quit', 'help']

###########################################################
# MAIN PROGRAM FUNCTION
###########################################################

#==========================================================
# Name:     runClient()
# Desc:     This function sets up a stream socket on the 
#           client machine which communicates with an
#           open socket on the server machine. The host and
#           port connection information is passed to the client
#           program itself as command line arguments which 
#           can only be determined after running the server. 
#           Once the client/server socket connection has
#           been established, the client runs a command-
#           line-like terminal UI in an infinite loop. The
#           client user can then issue various commands to
#           manipulate the files in the distributed file
#           system on the server, or exit the program.
# Params:   -
# Return:   -
#==========================================================
def runClient():

    # Client socket handle
    clientSocket = None

    # Find available socket address info
    for result in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):

        # Get socket addres info
        (family, socketType, proto, canonName, sockAddr) = result

        # Get socket handle; move to next addr info if cannot
        try:
            clientSocket = socket.socket(family, socketType, proto)
        except (OSError, socket.error):
            clientSocket = None
            continue

        # Connect to host machine; move to next addr info if cannot
        try:
            clientSocket.connect((HOST, PORT))
        except (OSError, socket.error):
            clientSocket.close()
            clientSocket = None
            continue

        # Exit loop once valid socket address info is obtained
        break

    # Check to see if client socket is established
    if clientSocket is None:
        printError('Client could not open socket. Check for invalid server connection arguments.')
        sys.exit(2)

    # Client terminal UI; runs in an infinite loop
    while True:

        # Get client input
        try:
            input = raw_input
        except NameError:
            pass
        clientInput = input('client> ')

        # Remove whitespace from input
        clientInput = str(clientInput)
        clientInput.strip()

        # Check if input is empty
        if not clientInput:
            continue

        # Split input into whitespace deliminated strings and store in list
        clientInputParts = clientInput.split()

        # Get first (command) element of input
        clientInputCmd = clientInputParts[0]

        # Command switch case
        if clientInputCmd in VALID_CMDS:
            if clientInputCmd == 'upload':
                processUpload(clientSocket, clientInputParts)
            elif clientInputCmd == 'download':
                processDownload(clientSocket, clientInputParts)
            elif clientInputCmd == 'delete':
                processDelete(clientSocket, clientInputParts)
            elif clientInputCmd == 'list':
                processList(clientSocket, clientInputParts)
            elif clientInputCmd == 'add':
                processAdd(clientSocket, clientInputParts)
            elif clientInputCmd == 'remove':
                processRemove(clientSocket, clientInputParts)
            elif clientInputCmd == 'quit':
                processQuit(clientSocket, clientInputParts)
            elif clientInputCmd == 'help':
                processHelp(clientInputParts)
            else:
                continue
        else:
            printError('Invalid command.\nType "help" to see a list of valid commands.')
            continue

###########################################################
# PRINT ERROR FUNCTIONS
###########################################################

#==========================================================
# Name:     printError()
# Desc:     This function takes an error message provived
#           as an argument and prints it out on the 
#           terminal interface.
# Params:   <str> user-defined error message
# Return:   -
#==========================================================
def printError(errorMsg):
    print('Error: ' + errorMsg)

#==========================================================
# Name:     printUsage()
# Desc:     This function takes a usage message provived
#           as an argument and prints it out on the 
#           terminal interface.
# Params:   <str> user-defined usage message for a command
# Return:   -
#==========================================================
def printUsage(usageMsg):
    print('usage: ' + usageMsg)

###########################################################
# PROCESS CLIENT COMMAND FUNCTIONS
###########################################################

#==========================================================
# Name:     processUpload()
# Desc:     This function handles the uploading of objects
#           from the client machine to the server machine.
#           After checking for the proper command usage,
#           the command is sent to the server for processing.
#           The server then returns the scp command that the
#           client can run to upload their file to the server.
# Params:   <list> command name and argument (usr/obj)
# Return:   None
#==========================================================
def processUpload(clientSocket, clientInputParts):

    usageMsg = 'upload [user/object]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]
    clientUsr = clientInputParts[1].partition('/')[0]
    clientObj = clientInputParts[1].partition('/')[2]

    if '/' not in clientArg:
        printError('Invalid argument format.\nUser and object names must be separated by a \'/\' character.')
        printUsage(usageMsg)
        return

    if not clientUsr:
        printError('Invalid argument format. Provide a user name.')
        printUsage(usageMsg)
        return

    if not clientObj:
        printError('Invalid argument format. Provide an object name.')
        printUsage(usageMsg)
        return

    if '/' in clientObj:
        printError('Object to be uploaded must be in current client directory.')
        return

    if not os.path.exists(clientObj):
        printError('Object to be uploaded does not exist on client machine.')
        return

    if os.path.getsize(clientObj) >= BUFFER_SIZE:
        printError('Object to be uploaded is too large.')
        return

    clientSocket.send(clientCmd + '|' + clientUsr + '/' + clientObj)
    result = clientSocket.recv(BUFFER_SIZE)

    try:
        subprocess.call(result, shell=True)
    except OSError:
        printError('Upload failed, please try again.')

#==========================================================
# Name:     processDownload()
# Desc:     This function handles the downloading of objects
#           from the server machine to the client machine.
#           After checking for the proper command usage,
#           the command is sent to the server for processing.
#           The server then returns the scp command that the
#           client can run to download their file from the server.
# Params:   <list> command name and argument (usr/obj)
# Return:   None
#==========================================================
def processDownload(clientSocket, clientInputParts):

    usageMsg = 'download [user/object]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]
    clientUsr = clientInputParts[1].partition('/')[0]
    clientObj = clientInputParts[1].partition('/')[2]

    if '/' not in clientArg:
        printError('Invalid argument format. User and object names must be separated by a \'/\' character.')
        printUsage(usageMsg)
        return

    if not clientUsr:
        printError('Invalid argument format. Provide a user name.')
        printUsage(usageMsg)
        return

    if not clientObj:
        printError('Invalid argument format. Provide an object name.')
        printUsage(usageMsg)
        return

    clientSocket.send(clientCmd + '|' + clientUsr + '/' + clientObj)
    result = clientSocket.recv(BUFFER_SIZE)
    
    try:
        subprocess.call(result, shell=True)

        # Display downloaded file content
        print('')
        print('Object \'' + clientObj + '\' content:')
        downloadedFile = open(clientObj, 'r')
        print(downloadedFile.read())
        downloadedFile.close()

    except OSError:
        printError('Download failed, please try again.')

#==========================================================
# Name:     processDelete()
# Desc:     This function tells the server machine to delete
#           an object that the client user specifies. After
#           checking for the proper command usage, the command
#           is sent to the server for processing. The server then
#           returns confirmation that the download was successful.
# Params:   <list> command name and argument (usr/obj)
# Return:   None
#==========================================================
def processDelete(clientSocket, clientInputParts):

    usageMsg = 'delete [user/object]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]
    clientUsr = clientInputParts[1].partition('/')[0]
    clientObj = clientInputParts[1].partition('/')[2]

    if '/' not in clientArg:
        printError('Invalid argument format. User and object names must be separated by a \'/\' character.')
        printUsage(usageMsg)
        return

    if not clientUsr:
        printError('Invalid argument format. Provide a user name.')
        printUsage(usageMsg)
        return

    if not clientObj:
        printError('Invalid argument format. Provide an object name.')
        printUsage(usageMsg)
        return

    clientSocket.send(clientCmd + '|' + clientUsr + '/' + clientObj)
    result = clientSocket.recv(BUFFER_SIZE)
    print(result)

#==========================================================
# Name:     processList()
# Desc:     This function tells the server machine to list
#           all objects that belong to a user that the client 
#           user specifies. After checking for the proper 
#           command usage, the command is sent to the server 
#           for processing. The server then returns a list of
#           objects that belong to the specified user. The
#           format for the output is similar to the Linux
#           command 'ls -lrt'.
# Params:   <list> command name and argument (usr)
# Return:   None
#==========================================================
def processList(clientSocket, clientInputParts):

    usageMsg = 'list [user]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]
    
    if '/' in clientArg:
        printError('Invalid argument format.')
        printUsage(usageMsg)
        return

    clientSocket.send(clientCmd + '|' + clientArg)
    result = clientSocket.recv(BUFFER_SIZE)
    print(result)

#==========================================================
# Name:     processAdd()
# Desc:     
# Params:   <str> server machine IP address to add
# Return:   None
#==========================================================
def processAdd(clientSocket, clientInputParts):

    usageMsg = 'add [disk]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]

    clientSocket.send(clientCmd + '|' + clientArg)
    result = clientSocket.recv(BUFFER_SIZE)
    print(result)

#==========================================================
# Name:     processRemove()
# Desc:     
# Params:   <str> server machine IP address to remove
# Return:   None
#==========================================================
def processRemove(clientSocket, clientInputParts):
    
    usageMsg = 'remove [disk]'

    if len(clientInputParts) != 2:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    clientCmd = clientInputParts[0]
    clientArg = clientInputParts[1]

    clientSocket.send(clientCmd + '|' + clientArg)
    result = clientSocket.recv(BUFFER_SIZE)
    print(result)

#==========================================================
# Name:     processQuit()
# Desc:     After checking for the proper command usage, the
#           client program is terminated.
# Params:   <list> command name and argument (None)
# Return:   None
#==========================================================
def processQuit(clientSocket, clientInputParts):

    usageMsg = 'quit'

    if len(clientInputParts) != 1:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return
    
    print('\nClient program terminated.\n')
    clientSocket.close()
    sys.exit(0)

#==========================================================
# Name:     processHelp()
# Desc:     After checking for the proper command usage, a
#           list of valid client commands are displayed.
# Params:   <list> command name and argument (None)
# Return:   None
#==========================================================
def processHelp(clientInputParts):

    usageMsg = 'help'

    if len(clientInputParts) != 1:
        printError('Invalid command format.')
        printUsage(usageMsg)
        return

    print('upload   [user/object]   upload object from client to server')
    print('download [user/object]   download object from server to client')
    print('delete   [user/object]   delete object from server')
    print('list     [user]          list all user\'s objects on server')
    print('quit                     terminate client program')
    print('help                     display all valid client commands')

###########################################################        
# EXECUTE CLIENT PROGRAM
###########################################################

try:
    # Run client
    runClient()

except KeyboardInterrupt:
    # Terminate program
    print('\nClient program terminated.\n')
    sys.exit(3)


