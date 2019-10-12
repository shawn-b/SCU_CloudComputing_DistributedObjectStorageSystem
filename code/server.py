#!/usr/bin/python2.7

###########################################################
#
# File:     server.py
#
# Desc:     A basic stream socket storage server program that handles
#           client connections and input, and returns the
#           appropriate response. 
# 
#           When run, this program establishes a TCP socket
#           and automatically finds an available port for
#           listening to client connections. The port number 
#           and server machine name and IP address are displayed 
#           so that a client can then establish a connection on 
#           their side. The server runs a separate thread for 
#           each client, allowing for more than one client to
#           be served at a given time. The server runs in an
#           infinite loop, waiting for more clients to connect.
#           
#           Each client thread also runs in an infinite loop,
#           until the client socket connection is terminated.
#           The client thread will listen for any client input
#           commands, process it, and send back the result. The
#           server supports the uploading, downloading, deleting, 
#           and listing of objects that belong to a particular
#           user (specified by the client).
#
# Author:   Shawn Bhagat
# Class:    COEN 241 - Cloud Computing
# 
###########################################################

###########################################################
# IMPORT NEEDED MODULES
###########################################################

import sys
import socket
import os
from threading import Thread
import traceback
import hashlib
import subprocess
import pipes

###########################################################
# DEFINE GLOBAL VARIABLES AND CONSTANTS
###########################################################

# Get partition power and server machine names from command line args
if len(sys.argv) < 4:
    print('usage: server [partition-power] [disk-1-name disk-2-name ...]')
    sys.exit(1)
else:
    partPwrTemp = sys.argv[1]

    if not partPwrTemp.isdigit():
        print('Error: Partition power must be a positive integer value.')
        sys.exit(2)

    if int(partPwrTemp) < 10 or int(partPwrTemp) > 24:
        print('Error: Partition power must be in the range of 10 to 24.')
        sys.exit(2)

    PART_PWR = int(partPwrTemp)     # partition power
    PART_CNT = 2 ** PART_PWR        # partition count
    SERVER_IPS = sys.argv[2:]       # list of server machine names/addresses

    # DEBUG IP lists
    # SERVER_IPS_D1 = ['129.210.16.80', '129.210.16.81', '129.210.16.83', '129.210.16.89']
    # SERVER_IPS_D2 = ['linux60999', '129.210.16.100', '129.210.16.83', '129.210.wph.77']

    # Check that all names/ip addr are valid and can be connected to
    allValidIPs = True
    for server in SERVER_IPS:
        try:
            socket.gethostbyname(server)
        except (socket.error, socket.herror):
            allValidIPs = False
            print('Error: Cannot connect to machine: ' + server)
    if not allValidIPs:
        sys.exit(3)

    # Check for server disk count (need at least one)
    if len(SERVER_IPS) < 1:
        print('Error: Need to provide at least one server disk for file storage.')
        sys.exit(4)

# Socket variables
BUFFER_SIZE = 4096      # max buffer size for send/recv data btwn client & server
BACKLOG = 10            # max number of clients that can be put in queue

# Device lookup tables
PRIMARY_PART_DISK_TBL = [None] * PART_CNT   # maps each partition with one of the server disk #s
BACKUP_PART_DISK_TBL = [None] * PART_CNT    # similar to primary table but different mappings

# Object lookup table
USER_OBJ_TRACKER = {}   # holds list of users with their associated files on server

# Partition-UserObject lookup table
PART_OBJ_TRACKER = {}   # holds the user/object values associated with each partition
                        # used for transferring objects btwn disks for disk operations
                        # key: partition #; value: usr/obj pair

# Personal path for tmp folder on server machines
MY_TMP_PATH = '/tmp/sbhagat/'
CURRENT_USR = os.environ['USER']

# Command constants
CMD_SUCCESS = 0
CMD_FAILURE = 1

###########################################################
# MAIN PROGRAM FUNCTION
###########################################################

#==========================================================
# Name:     runServer()
# Desc:     This function sets up a stream socket on the 
#           server machine, as well as automatically finds
#           an available port through which the client
#           program(s) can connect. This information, along 
#           with the server name/IP address, is displayed.
#           Once the socket and port have been established,
#           it runs in an infinite loop, in which it accepts
#           cliet connections and branches them off to be 
#           handled in their own thread execution.
# Params:   -
# Return:   -
#==========================================================
def runServer():

    # Server socket handle
    serverSocket = None
    
    # Connection variables
    HOST = None     # will be whatever machine this program is running on
    PORT = 3333     # temp value; server will automatically find an available port

    # Loop through socket address info until one is valid and available
    for result in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):

        # Get socket addres info
        (family, socketType, proto, canonName, sockAddr) = result

        # Get socket handle; move to next addr info if cannot
        try:
            serverSocket = socket.socket(family, socketType, proto)
        except (OSError, socket.error):
            serverSocket = None
            continue

        # Associate socket with port on local machine; move to next addr info if cannot
        try:
            serverSocket.bind((socket.gethostname(), 0))
        except (OSError, socket.error):
            serverSocket.close()
            serverSocket = None
            continue

        # Exit loop once valid socket address info has been gotten
        break

    # Check to see if socket address info was found and socket established
    if serverSocket is None:
        print('Error! Server could not open socket.')
        sys.exit(5)

    # Start listening for client connections on socket
    serverSocket.listen(BACKLOG)

    # Get connection info
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    port_no = serverSocket.getsockname()[1]

    # Print server info so client(s) can connect
    print('')
    print('########################################')
    print('# SERVER CONNECTION INFORMATION')
    print('########################################')
    print('# host: ' + str(host_name) + " or " + str(host_ip))
    print('# port: ' + str(port_no))
    print('########################################')
    print('')

    # Run server indefinitely
    while True:

        print('Server is listening for client connections...')

        # Get a pending client cxn
        (clientSocket, clientAddress) = serverSocket.accept()

        # Client info
        print('Client info:', clientAddress)

        # Set up client thread
        try:
            Thread(target=clientThread, args=(clientSocket,)).start()
        except:
            traceback.print_exc()

###########################################################
# SERVER SETUP FUNCTION
###########################################################

#==========================================================
# Name:     setupDeviceLookupTables()
# Desc:     This function divides the total number of partitions
#           roughly equally between the server machines
#           specified in the server command line arguments.
#           The function loops through each of the server
#           machines and sets up its temporary directory in
#           which the clients' objects will be stored. Also,
#           a device lookup table is filled, mapping each 
#           partition to one of the server machines. This table
#           is used later for finding the server upon which a
#           client user object is stored.
# Params:   -
# Return:   -
#==========================================================
def setupDeviceLookupTables(pPartDiskTbl, bPartDiskTbl):
    
    # Get disk-related variables
    servDiskCnt = len(SERVER_IPS)
    servDiskPartCnt = PART_CNT / servDiskCnt

    # Define start/end indexes for specifying partition ranges 
    startIdx = 0
    endIdx = startIdx + servDiskPartCnt

    # Iterate through all server disks
    for diskNo in range(0, servDiskCnt):

        # Get disk IP
        diskIP = str(SERVER_IPS[diskNo])

        # Build host name
        host = CURRENT_USR + '@' + diskIP

        # Set up tmp directory on server disk
        dirExistTestCmd = ['ssh', host, 'test', '-e', pipes.quote(MY_TMP_PATH)]
        tmpDirExists = subprocess.call(dirExistTestCmd)
        if tmpDirExists == 0:
            print('Tmp directory already exists on server machine: ' + diskIP)
        else:
            print('Creating tmp directory on server machine: ' + diskIP)
            mkTmpDirCmd = ['ssh', CURRENT_USR + '@' + diskIP, 'mkdir', MY_TMP_PATH]
            subprocess.call(mkTmpDirCmd)

        # Iterate through partition range for this disk
        for p in range(startIdx, endIdx):

            # Assign disk number to primary device lookup table
            pPartDiskTbl[p] = diskNo

            # Assign disk number to backup device lookup table
            if diskNo == (servDiskCnt - 1):
                bPartDiskTbl[p] = 0
            else:
                bPartDiskTbl[p] = diskNo + 1
        
        # Increment range to next disk partition numbers     
        startIdx += servDiskPartCnt
        endIdx += servDiskPartCnt

###########################################################
# CLIENT HANDLING FUNCTIONS
###########################################################

#==========================================================
# Name:     getDiskNo()
# Desc:     This function returns the IP address of a 
#           server machine, given a client user object name.
#           The object string is hashed with an md5sum
#           algorithm, and is mapped to one of the partitions.
#           This partition number acts as the index for the 
#           device lookup table that is set up in the 
#           setupDeviceLookupTables() function. The table can
#           then be used to find the associated server machine
#           IP address.
# Params:   <str> client user name and object name ('user/object')
# Return:   <str>  IP address of server machine that object is stored
#==========================================================
def getDiskNo(clientUsrObj):
    
    # Perform hash
    hashKey = hashlib.md5(clientUsrObj).hexdigest()

    print('long hash key:  ' + hashKey)

    # Number of bits in md5sum hash result
    HASH_KEY_BIT_CNT = 128

    # Shift key to get a more manageable hash index (0 to 2^partitionPwr)
    hashKeyDec = int(hashKey, 16)
    shiftAmt = HASH_KEY_BIT_CNT - PART_PWR
    objIdx = hashKeyDec >> shiftAmt

    # CHECKME: should the above be a left shift '<<' instead?

    print('short hash key: ' + hex(objIdx) + '\n')

    # Get disk IP addresses using device lookup tables
    primDiskNo = PRIMARY_PART_DISK_TBL[objIdx]
    primDiskIP = SERVER_IPS[primDiskNo]
    backDiskNo = BACKUP_PART_DISK_TBL[objIdx]
    backDiskIP = SERVER_IPS[backDiskNo]

    # Return disk IP address
    return(primDiskIP, backDiskIP)

#==========================================================
# Name:     clientThread()
# Desc:     This function handles the execution of the
#           client thread, which runs in an infinite loop
#           until the connection is terminated. It receives
#           client input, hands it off to be processed, and 
#           and send the result back to the client. There is
#           also a check to see if the server is sending back 
#           an amount of data that is too large.
# Params:   <socket> client socket connection
# Return:   -
#==========================================================
def clientThread(clientSocketCxn):

    try:
        # Maintain infinite cxn with client until terminated
        while True:

            # Get client input
            clientInput = clientSocketCxn.recv(BUFFER_SIZE)

            # Process input
            serverOutput = processClientInput(clientInput)

            # Check size of server output; send response if valid size
            if sys.getsizeof(serverOutput) < BUFFER_SIZE:

                # Send result back to client
                clientSocketCxn.sendall(serverOutput)

            else:
                print('ERROR: Server result is too large to transmit, try again.\n')
                continue
            
            print('')

    except socket.error:
        # Close connection if client socket disconnects
        print('Server terminated client connection.')
        clientSocketCxn.close()

#==========================================================
# Name:     processClientInput()
# Desc:     This function takes the raw client input and
#           determines which function should handle its
#           execution. It currently supports the following
#           client commands: upload, download, delete, list, 
#           add, and remove.
# Params:   <str> client input command and argument
# Return:   <str> command ouput, or error message
#==========================================================
def processClientInput(clientInput):

    # List of valid client commands
    VALID_CMDS = ['upload', 'download', 'delete', 'list', 'add', 'remove']

    # Split input into list of two strings, separated by '|' character
    clientInputParts = clientInput.partition('|')

    # Get first (command) element of input list
    clientInputCmd = clientInputParts[0]

    # Get third (argument) element of input list
    clientInputArg = clientInputParts[2]

    # Command switch case
    if clientInputCmd in VALID_CMDS:

        print('')
        print('============================================================')
        print('COMMAND: ' + clientInputCmd + '\n')

        if clientInputCmd == 'upload':
            return(processUpload(clientInputArg))
        elif clientInputCmd == 'download':
            return(processDownload(clientInputArg))
        elif clientInputCmd == 'delete':
            return(processDelete(clientInputArg))
        elif clientInputCmd == 'list':
            return(processList(clientInputArg))
        elif clientInputCmd == 'add':
            return(processAdd(clientInputArg))
        elif clientInputCmd == 'remove':
            return(processRemove(clientInputArg))
        else:
            return('Command cannot be processed by server.')
    else:
        return('Command cannot be processed by server.')

#==========================================================
# Name:     processUpload()
# Desc:     This function creates a directory for the user
#           on the appropriate server machine, which stores
#           their objects' data. It returns the scp command
#           to be be run on the client machine, to reduce 
#           the issue of a possible server bottleneck.
# Params:   <str> client input command and argument
# Return:   <str> scp command to be executed by client
#==========================================================
def processUpload(clientInputArg):
    
    # Get client user name and object name from command argument
    clientUsr = clientInputArg.partition('/')[0]
    clientObj = clientInputArg.partition('/')[2]

    # Get disk IP adress on which user's file is stored
    (primDiskIP, backDiskIP) = getDiskNo(clientInputArg)

    # Build host name
    pHost = CURRENT_USR + '@' + primDiskIP
    bHost = CURRENT_USR + '@' + backDiskIP

    # Path to user folder on server machine
    usrDirPath = MY_TMP_PATH + clientUsr

    # Create user directory on primary server disk
    print('Create user directories on server machines:')

    dirExistTestCmd = ['ssh', pHost, 'test -e ' + pipes.quote(usrDirPath)]
    usrDirExists = subprocess.call(dirExistTestCmd)
    if usrDirExists == 0:
        print('Primary machine (dir already exists): ' + primDiskIP)
    else:
        print('Primary machine (new dir): ' + primDiskIP)
        mkUsrDirCmd = ['ssh', pHost, 'mkdir', usrDirPath]
        subprocess.call(mkUsrDirCmd)

    # Create user directory on backup server disk
    dirExistTestCmd = ['ssh', bHost, 'test -e ' + pipes.quote(usrDirPath)]
    usrDirExists = subprocess.call(dirExistTestCmd)
    if usrDirExists == 0:
        print('Backup machine (dir already exists):  ' + backDiskIP)
    else:
        print('Backup machine (new dir):  ' + backDiskIP)
        mkUsrDirCmd = ['ssh', bHost, 'mkdir', usrDirPath]
        subprocess.call(mkUsrDirCmd)

    print('')
    
    # Check to see if user exists in object tracker table; if not, add
    if USER_OBJ_TRACKER.get(clientUsr) is None:
        USER_OBJ_TRACKER[clientUsr] = []

    # Check to see if object already exists for user
    if clientObj in USER_OBJ_TRACKER.get(clientUsr):
        return('echo "User object already exists. Please rename or delete object and upload."')

    # Add object to user-object tracker table
    USER_OBJ_TRACKER[clientUsr].append(clientObj)

    # Print all of user's objects
    print('All user \'' + clientUsr + '\' objects: ' + str(USER_OBJ_TRACKER.get(clientUsr)))

    # Add object to partition-object tracker table
    hashKey = hashlib.md5(clientUsr + '/' + clientObj).hexdigest()
    objIdx = int(hashKey, 16) >> (128 - PART_PWR)
    PART_OBJ_TRACKER[objIdx] = (clientUsr, clientObj)

    # Print partition associated with new object
    print('User obj \'' + clientObj  + '\' partition #: ' + str(objIdx) + '\n')

    # Return scp command to be executed by client
    return('scp -B ' + clientObj + ' ' +  CURRENT_USR + '@' + str(primDiskIP) + ':' + MY_TMP_PATH + clientUsr + '; ' + 'scp -B ' + clientObj + ' ' +  CURRENT_USR + '@' + str(backDiskIP) + ':' + MY_TMP_PATH + clientUsr)

#==========================================================
# Name:     processDownload()
# Desc:     This function checks to see if the specified user
#           and object exist. If so, it returns the scp command
#           to be be run on the client machine, to reduce 
#           the issue of a possible server bottleneck. If not,
#           it returns an error message command to be outputted 
#           on the client machine.
# Params:   <str> client input command and argument
# Return:   <str> scp/error command to be executed by client
#==========================================================
def processDownload(clientInputArg):
    
    # Get client user name and object name from command argument
    clientUsr = clientInputArg.partition('/')[0]
    clientObj = clientInputArg.partition('/')[2]

    # Check to see if user exists in object tracker table
    if USER_OBJ_TRACKER.get(clientUsr) is not None:

        # Print object to download
        print('User object to download: ' + clientObj + '\n')

        # Check to see if object exists in object tracker table
        if clientObj in USER_OBJ_TRACKER.get(clientUsr):
            
            # Get disk IP adress on which user's file is stored
            (primDiskIP, backDiskIP) = getDiskNo(clientInputArg)
            diskIP = validateObjectExistence(clientUsr, clientObj, primDiskIP, backDiskIP)

             # Check if server IP exists (aka: file was or was not recovered properly)
            if not diskIP:
                return('echo "Object \'' + clientObj + '\' could not be retrieved from server."')

            # Return scp download command to be executed by client
            return('scp -B ' + CURRENT_USR + '@' + str(diskIP) + ':' + MY_TMP_PATH + clientUsr + '/' + clientObj + ' .')

        else:
            return('echo "ERROR: Object does not exist on server."')
    else:
        return('echo "ERROR: User has no objects stored on server."')

#==========================================================
# Name:     processDelete()
# Desc:     This function checks to see if the specified user
#           and object exist. If so, it lazy deletes the object.
#           This means that the actual object still exists, it
#           is just marked as deleted. If the object is not deleted,
#           the function returns an error message to be printed 
#           on the client machine.
# Params:   <str> client input command and argument
# Return:   <str> success/error message to be printed by client
#==========================================================
def processDelete(clientInputArg):
    
    # Get client user name and object name from command argument
    clientUsr = clientInputArg.partition('/')[0]
    clientObj = clientInputArg.partition('/')[2]

    # Check to see if user exists in object tracker table
    if USER_OBJ_TRACKER.get(clientUsr) is not None:

        # Check to see if object exists in object tracker table
        if clientObj in USER_OBJ_TRACKER.get(clientUsr):

            # Print all of user's objects before removal
            print('All user \'' + clientUsr + '\' objects (before): ' + str(USER_OBJ_TRACKER.get(clientUsr)) + '\n')
            
            # Remove from object tracker table (lazy delete)
            USER_OBJ_TRACKER[clientUsr].remove(clientObj)

            # Print all of user's objects after removal
            print('All user \'' + clientUsr + '\' objects (after):  ' + str(USER_OBJ_TRACKER.get(clientUsr)) + '\n')

            # Return success message
            return('Object \'' + clientObj + '\' has been deleted.')
        else:
            return('ERROR: File does not exist.')
    else:
        return('ERROR: User does not exist.')

#==========================================================
# Name:     processList()
# Desc:     This function checks to see if the user is in the
#           system. If so, it then loops through all the user's
#           associated objects, and then gets their metadata
#           from the server machines upon which they are stored.
#           The final output is then reordered and formatted to
#           matched the format of the Linux 'ls -lrt' command.
# Params:   <str> client input command and argument
# Return:   <str> list output or error message to be printed by client
#==========================================================
def processList(clientInputArg):
    
    # Get client user name from command argument
    clientUsr = clientInputArg

    # Print user
    print('For user: ' + clientUsr + '\n')

    # Check to see if user exists in system
    if USER_OBJ_TRACKER.get(clientUsr) is None:
        return('User has no files on server.')

    # Check to see if user exists but has no files on system
    elif (USER_OBJ_TRACKER.get(clientUsr) is not None) and (not USER_OBJ_TRACKER.get(clientUsr)):
        return('User has no files on server.')

    # Get all user's files if available
    else:
        # Get list of user objects from object tracker table
        allUserObjNames = USER_OBJ_TRACKER[clientUsr]

        # Print all of user's objects
        print('All user \'' + clientUsr + '\' objects: ' + str(USER_OBJ_TRACKER.get(clientUsr)) + '\n')

        # Get metadata for each of user's objects
        lsCmdFullOutput = []
        for clientObj in allUserObjNames:

            # Print current user object
            print('Current object: ' + clientObj + '\n')

            # Get disk IP that object is stored on
            key = clientUsr + '/' + clientObj
            (primDiskIP, backDiskIP) = getDiskNo(key)
            diskIP = validateObjectExistence(clientUsr, clientObj, primDiskIP, backDiskIP)
            
            # Check if server IP exists (aka: file was or was not recovered properly)
            if not diskIP:
                return('Object \'' + clientObj + '\' could not be accessed on server.')

            # SSH to specified server machine and get 'ls -l' command content
            #lsCmd = 'ssh ' + CURRENT_USR + '@' + diskIP + ' ls -l ' + MY_TMP_PATH + clientUsr + '/"' + clientObj + '"'
            lsCmd = ['ssh', CURRENT_USR + '@' + diskIP, 'ls', '-l', MY_TMP_PATH + clientUsr + '/"' + clientObj + '"']
            lsCmdResult = subprocess.check_output(lsCmd)
            lsCmdFullOutput.append(lsCmdResult)

        # Parse output for easy sorting to match 'ls -lrt' command format
        lsCmdFullOutputParsed = []
        for lsOutput in lsCmdFullOutput:
            lsOutputParts = str(lsOutput).split()
            miscOutput = ' '.join(lsOutputParts[0:5])
            dateOutput = ' '.join(lsOutputParts[5:8])
            fileOutput = lsOutputParts[8]
            lsCmdFullOutputParsed.append((miscOutput, dateOutput, fileOutput))

        # Sort by time first (newest first), then obj name second (desc order)
        lsCmdFullOutputSorted = sorted(lsCmdFullOutputParsed, key=lambda x: (x[1], x[2]), reverse=True)

        # Rejoin fragmented output parts
        lsCmdFullOutputFinalResult = []
        for lsOutput in lsCmdFullOutputSorted:
            lsCmdFullOutputFinalResult.append(lsOutput[0] + ' ' + lsOutput[1] + ' ' + lsOutput[2])

        # Join all object data into a single string (from original list: lsCmdFullOutput[])
        lsCmdFullOutputFinalResult = '\n'.join(lsCmdFullOutputFinalResult)

        # Return list and metadata of objects belonging to user (on all server disks)
        return(lsCmdFullOutputFinalResult)

#==========================================================
# Name:     processAdd()
# Desc:     The function first checks to see if the provided
#           IP address is associated with a valid machine on
#           the network, and can connect to it. If it passes,
#           it sets up the necessary directory structure on the
#           machine. It then adds the IP address to the main
#           IP list data structure and requests the disks to
#           be repartitioned.
# Params:   <str> client input disk IP address
# Return:   <str> error messages or list of file transfers
#==========================================================
def processAdd(clientInputArg):

    # Get new disk IP address from command argument
    newDiskIP = clientInputArg

    # Check to see if machine is already part of server cloud network
    if newDiskIP in SERVER_IPS:
        return('Error: Server disk already exists on network.')

    # TODO: Impose upper limit of number of machines on cloud network

    # Check if new machine even exists on network, if not already
    try:
        socket.gethostbyname(server)
    except (socket.error, socket.herror):
        return('Error: Server disk does not exist on network.')

    # Check if program can interact/ssh to machine
    newHost = CURRENT_USR + '@' + newDiskIP
    tmpDirPath = '/tmp/'
    testDirCmd = ['ssh', newHost, 'test', '-e', pipes.quote(tmpDirPath)]
    tmpDirStatus = subprocess.call(testDirCmd)

    # Create tmp directory on new machine
    if tmpDirStatus == CMD_SUCCESS:

        # Check if full temp path exists on machine (aka, MY_TMP_PATH)
        fullTmpDirCmd = ['ssh', newHost, 'test', '-e', pipes.quote(MY_TMP_PATH)]
        fullTmpDirStatus = subprocess.call(fullTmpDirCmd)

        if fullTmpDirStatus == CMD_FAILURE:
            mkFullTmpDirCmd = ['ssh', CURRENT_USR + '@' + newDiskIP, 'mkdir', MY_TMP_PATH]
            subprocess.call(mkFullTmpDirCmd)
        else:
            print('Server object storage already set up.')
    else:
        return('Error: Could not establish SSH connection to new server disk.')

    # After all validation checking, add new server IP to SERVER_IPS list
    SERVER_IPS.append(newDiskIP)

    # Redistribute partitions and existing objects to share with new disk
    repartitionResultChanges = repartitionServerDisks(PRIMARY_PART_DISK_TBL, BACKUP_PART_DISK_TBL, newDiskIP)

    # Return repartition changes
    return(repartitionResultChanges)

#==========================================================
# Name:     processRemove()
# Desc:     The function first checks to see if the machine
#           associated with the provided IP address is valid.
#           If so, it then removes the IP address from the main
#           IP list data structure and requests the disks to
#           be repartitioned.
# Params:   <str> client input disk IP address
# Return:   <str> error messages or list of file transfers   
#==========================================================
def processRemove(clientInputArg):

    # Get IP address of disk to be removed from command argument
    oldDiskIP = clientInputArg

    # Check if IP address exists in SERVER_IPS list
    if oldDiskIP not in SERVER_IPS:
        return('Error: Server disk does not exist on network.')

    # There need to be at least two server machines at all times
    if len(SERVER_IPS) < 3:
        return('Error: Cannot remove disk. At least two server machines must be online.')

    # If passes checks, remove from list
    SERVER_IPS.remove(oldDiskIP)

    # If disk does exist, redistribute partitions and existing objects to fill empty indexes
    repartitionResultChanges = repartitionServerDisks(PRIMARY_PART_DISK_TBL, BACKUP_PART_DISK_TBL, oldDiskIP)

    # Return repartition changes
    return(repartitionResultChanges)

#==========================================================
# Name:     validateObjectExistence()
# Desc:     This function gets the IP address of a machine
#           that the specified user object is on. It also 
#           checks the existence of the primary and backup
#           copies the object has on the server. If either 
#           does not exist, it will request that object to
#           be restored using an existing working copy.
# Params:   <str> user name
#           <str> object name
#           <str> server machine which stores primary copy of object
#           <str> server machine which stores backup copy of object
# Return:   <str> server machine IP from where to access object 
#           <None> if recovery fails or object doesn't exist on either machine
#==========================================================
def validateObjectExistence(usr, obj, pDiskIP, bDiskIP):

    # FIXME: rename function getObjectLocation()

    # Build path to user's object's location
    usrPath = MY_TMP_PATH + usr + '/' + obj

    # Check existence of object on primary disk
    pDiskHost = CURRENT_USR + '@' + pDiskIP
    testCmd = ['ssh', pDiskHost, 'test', '-f', pipes.quote(usrPath)]
    pStatus = subprocess.call(testCmd)

    # Check existence of object on backup disk
    bDiskHost = CURRENT_USR + '@' + bDiskIP
    testCmd = ['ssh', bDiskHost, 'test', '-f', pipes.quote(usrPath)]
    bStatus = subprocess.call(testCmd)

    # Debug: print test file existence status
    print('Status of object\'s primary and backup copies (failures will be restored):')
    print('PRIM Status[' + pDiskHost + ']: ' + ('success' if pStatus == CMD_SUCCESS else 'failure'))
    print('BCKP Status[' + bDiskHost + ']: ' + ('success' if pStatus == CMD_SUCCESS else 'failure'))
    print('')

    # Case #1: object exists on both disks
    if pStatus == CMD_SUCCESS and bStatus == CMD_SUCCESS:
        return pDiskIP

    # Case #2: object only exists on primary disk
    if pStatus == CMD_SUCCESS and bStatus == CMD_FAILURE:
        if recoverObject(usr, obj, pDiskIP, bDiskIP):
            return pDiskIP
        else:
            return None

    # Case #3: object only exists on backup disk
    if pStatus == CMD_FAILURE and bStatus == CMD_SUCCESS:
        if recoverObject(usr, obj, bDiskIP, pDiskIP):
            return bDiskIP
        else:
            return None

    # Case #4: object does not exist on either disk
    if pStatus == CMD_FAILURE and bStatus == CMD_FAILURE:
        return None

#==========================================================
# Name:     recoverObject()
# Desc:     This function transfers a user's object from one
#           server machine to another (specified in the args).
#           It makes sure that the disk that the file is being
#           transferred to has the proper user directory set
#           up.
# Params:   <str> user name
#           <str> object name
#           <str> server machine which has intact object
#           <str> server machine that is missing object
# Return:   <bool> True if obj recovery was successful, False if not
#==========================================================
def recoverObject(usr, obj, sourceIP, destIP):

    # Build path to user's object's location
    usrDirPath = MY_TMP_PATH + usr
    usrPath = MY_TMP_PATH + usr + '/' + obj

    # Build host names
    srcDiskHost = CURRENT_USR + '@' + sourceIP
    dstDiskHost = CURRENT_USR + '@' + destIP

    # Check to see if destination machine has user directory; if not, create it
    dirExistTestCmd = ['ssh', dstDiskHost, 'test -e ' + pipes.quote(usrDirPath)]
    usrDirExists = subprocess.call(dirExistTestCmd)
    if usrDirExists == 0:
        print('User dir already exists on destination machine.\n')
    else:
        print('Create user dir on destination machine: ' + dstDiskHost + '\n')
        mkUsrDirCmd = ['ssh', dstDiskHost, 'mkdir', usrDirPath]
        subprocess.call(mkUsrDirCmd)

    # TODO: If user dir cannot be (or is not already) created, do not perform transfer and return False

    # Build command
    srcDisk = srcDiskHost + ':' + usrPath
    dstDisk = dstDiskHost + ':' + usrPath
    cpyCmdArgs = ['scp', '-3', srcDisk, dstDisk]
    cpyCmdStatus = subprocess.call(cpyCmdArgs)

    # Return confirmation (True is successful, False if not)
    if cpyCmdStatus == 0:
        return True
    else:
        return False

#==========================================================
# Name:     repartitionServerDisks()
# Desc:     This function re-maps the partition and server
#           disk number relationships. It requests object
#           trasfers between server machines if the new
#           mapping differs from the original machine.
# Params:   <list> device lookup table for primary object copies
#           <list> device lookup table for backup object copies
#           <str> IP address of disk that was added/removed
# Return:   <str> list of object transfers performed
#==========================================================
def repartitionServerDisks(pPartDiskTbl, bPartDiskTbl, diskIP):

    # FIXME: Use function parameters
    
    # List to hold the information of all the disk/object trasfers that occurred during repartitioning
    changeTracker = []

    # Create new device lookup tables
    NEW_PRIMARY_PART_DISK_TBL = [None] * PART_CNT
    NEW_BACKUP_PART_DISK_TBL = [None] * PART_CNT
    setupDeviceLookupTables(NEW_PRIMARY_PART_DISK_TBL, NEW_BACKUP_PART_DISK_TBL)

    # Iterate through partitions
    for p in range(0, PART_CNT):

        # Compare server disk numbers (index) for primary object copies
        if PRIMARY_PART_DISK_TBL[p] != NEW_PRIMARY_PART_DISK_TBL[p]:
            PRIMARY_PART_DISK_TBL[p] = NEW_PRIMARY_PART_DISK_TBL[p]

        # Compare server disk numbers (index) for backup object copies
        if BACKUP_PART_DISK_TBL[p] != NEW_BACKUP_PART_DISK_TBL[p]:
            BACKUP_PART_DISK_TBL[p] = NEW_BACKUP_PART_DISK_TBL[p]

        # Check to see if a user's object is stored at that partition
        if PART_OBJ_TRACKER.get(p) is not None:

            # Get user and object values
            (usr, obj) = PART_OBJ_TRACKER[p]

            # General transfer info to tracker
            usrObj = usr + '/' + obj
            pSrcDisk = SERVER_IPS[PRIMARY_PART_DISK_TBL[p]]
            pDstDisk = SERVER_IPS[NEW_PRIMARY_PART_DISK_TBL[p]]
            bSrcDisk = SERVER_IPS[BACKUP_PART_DISK_TBL[p]]
            bDstDisk = SERVER_IPS[NEW_BACKUP_PART_DISK_TBL[p]]

            # Compare server disk IP address for primary object copies
            if SERVER_IPS[PRIMARY_PART_DISK_TBL[p]] != SERVER_IPS[NEW_PRIMARY_PART_DISK_TBL[p]]:
                #changeTracker.append('PRIM: <' + usrObj  + '>; ' + pSrcDisk + ' -> ' + pDstDisk)
                print('PRIM: <' + usrObj  + '>; ' + pSrcDisk + ' -> ' + pDstDisk)
                recoverObject(usr, obj, SERVER_IPS[PRIMARY_PART_DISK_TBL[p]], SERVER_IPS[NEW_PRIMARY_PART_DISK_TBL[p]])
                
            # Compare server disk IP address for primary object copies
            if SERVER_IPS[BACKUP_PART_DISK_TBL[p]] != SERVER_IPS[NEW_BACKUP_PART_DISK_TBL[p]]:
                #changeTracker.append('BCKP: <' + usrObj  + '>; ' + bSrcDisk + ' -> ' + bDstDisk)
                print('BCKP: <' + usrObj  + '>; ' + bSrcDisk + ' -> ' + bDstDisk)
                recoverObject(usr, obj, SERVER_IPS[BACKUP_PART_DISK_TBL[p]], SERVER_IPS[NEW_BACKUP_PART_DISK_TBL[p]])
            
    # Check to see if any objects were transferred
    return('Disk repartitioning complete.')

###########################################################        
# EXECUTE SERVER PROGRAM
###########################################################

try:
    # Set up device lookup tables
    setupDeviceLookupTables(PRIMARY_PART_DISK_TBL, BACKUP_PART_DISK_TBL)

    # Run server
    runServer()

except KeyboardInterrupt:
    # Terminate program
    print('\nServer program terminated.\n')
    sys.exit(6)