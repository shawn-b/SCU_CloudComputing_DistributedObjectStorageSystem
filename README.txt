===============================================================================
README
===============================================================================

Read the Design Document (DesignDoc.txt) for a full description of the 
application overview, program structure and design, and client and server 
input/output.

-------------------------------------------------------------------------------
NAME
    client.py - runs a stream socket client program (run after server starts)
SYNOPSIS
    client.py [host-name|host-IP-address] [port]
DESCRIPTION
    [host]  can be either host name or IP address;
            obtained when server program is run
    [port]  is the port on which the server is listening for clients;
            obtained when server program is run
    
    Client user commands once program is running:
    - 'upload <user/file>'      -> upload file from client to server
    - 'download <user/file>'    -> download file from server to client
    - 'delete <user/file>'      -> delete file from server
    - 'list <user>'             -> list all of a user's files on the server
    - 'add <disk>'              -> adds new server machine to application
    - 'remove <disk>'           -> removes an existing server machine being used by application
    - 'quit'                    -> terminate program
    - 'help'                    -> display all valid client commands
    - 'ctrl+c'                  -> terminate program

    Exit status:
    - 0     -> if program terminated properly
    - 1     -> if command line argument format is not valid
    - 2     -> if client socket connection cannot be establised
    - 3     -> if client terminates using keyboard interrupt (ie. ctrl+c)
-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
NAME
    server.py - runs a stream socket server program (run before client starts)
SYNOPSIS
    server.py [partition-power] [disk-1-name disk-2-name ...]
DESCRIPTION
    [partitionpower]    used to specify number of partitions server will have
    [disk1name ...]     the name or IP address of at least two server machines
                        on which user data (and their backups) will be stored

    Exit status:
    - 1     -> if incorrect number of command line arguments
    - 2     -> if partition power format is invalid
    - 3     -> if one or more of the server machine names/addresses are invalid 
    - 4     -> if less than one server disk has been specified
    - 5     -> if server socket connection cannot be establised
    - 6     -> if server terminates using keyboard interrupt (ie. ctrl+c)
-------------------------------------------------------------------------------