import boto3
import socket
import sys
import time
import os
import xmlrpclib
from threading import Thread, Lock
from thread import *
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import re
from modules import dnRPCClient


# NOTE:  The '#' is not allowed in filename because it's used for blockID stuff
reservedChar = ["#", "<", ">", ":", "/", "\\", "|", "?", "*"]

class NameNode:
    """
    Namenode needs to do two things
    1) Which blocks are part of which files
    2) Picking N different Datanodes to store each block (then return list of blocks and datanodes)
    3) only one writer at a time so we need a lock and thread for writeFile
    """
    def __init__(self, myIp):
        self.REPLICATION = 3 # pick 3 different datanodes to store each block by default
        self.fileD = {} # Dictionary for which blocks are part of which file
        self.blockD = {} # Dictionary for which datanodes are storing each block
        self.alive = {} # Dict for alive datanodes
        self.dnToBlock = {}
        self.mutex = Lock()
        self.contentsInDir = {"/home/": []}
        self.startThreads()
        self.ip = myIp


    # Create a file
    # Example of how to call the function:      createFile("/home/st/", "text1.txt")
    def createFile(self, path, filename):
        # Check if the filename is valid.  This prevents causing Exception on ec2 instance
        # NOTE:  The '#' is not allowed in filename because it's used for blockID stuff
        if re.match("^[\w,\s-]+\.[A-Za-z]{3}$", filename):
            if path in self.contentsInDir:
                if file in self.contentsInDir[path]:
                    return "File exists"
                else:
                    self.contentsInDir[path].append(filename)
                    # when the file is created, an S3 object should be specified
                    # and the data from S3 should be written into the file__________________________
                    return "Successfully created a file"
            else:
                return "Fail to create a file because the directory doesn't exist"
        else:
            return "Invalid filename"



    # Delete a file
    # Example of how to call the function:      deleteFile("/home/st/", "text.txt")
    def deleteFile(self, path, filename):
        if path in self.contentsInDir:
            if filename in self.contentsInDir[path]:
                # delete the file (blocks) in DataNodes________________________________________
                self.contentsInDir[path].remove(filename)
                return "Successfully delete a file"
            else:
                return "File doesn't exist"
        else:
            return "No such directory"



    # Create a directory
    # Example of how to call the function:   mkdir("/home/", "st")
    def mkdir(self, path, dir):
        if any(char in dir for char in reservedChar):
            return "Name of directory cannot any of reserved characters"
        if path in self.contentsInDir:
            self.contentsInDir[path + dir + "/"] = []
            self.contentsInDir[path].append(dir)
            return "Successfully created a directory"
        else:
            return "Fail to create a directory"



    # Example of how to call the function:     deleteDirectory("/home/st/")
    def deleteDirectory(self, path):
        if path == "/home/":
            return "You can't delete the root folder"
        if path in self.contentsInDir:
            # 1. look at the list and delete all the files_________________________________
            #    Note: Ignore if there is a sub-directory, it will be delete in the for loop
            print("List of files need to delete: ", self.contentsInDir[path])
            del self.contentsInDir[path]

            # 2. check if there is sub-directory in the current "path"
            #    If there is, delete it.
            for key in self.contentsInDir.keys():
                if path in key:
                    # 3. look at the list and delete all the files__________________________
                    print("List of files need to delete: ", self.contentsInDir[key])
                    del self.contentsInDir[key]

            # 3. Remove the directory from parent directory
            index = 0
            # Find the parent path
            for i, val in enumerate(path[:-1]):  # exclude the last "/"
                if val == "/":
                    index = i

            parentDir = path[: index+1]
            delDirName = path[index+1 : len(path)-1]
            self.contentsInDir[parentDir].remove(delDirName)

        return 'Removed ' + path



    # List the contents of a directory
    # Example of how to call the function:     ls("/home/")
    def ls(self, path):
        result = list()
        for key in self.contentsInDir:
            if key == path:
                for content in self.contentsInDir[key]:
                    print(content)
                    result.append(content)
        return result

# mkdir("/home/", "hang")
# printDic()
# print("")
#
# mkdir("/home/hang/", "nguyen")
# printDic()
# print("")
#
# deleteDirectory("/home/hang/")
# printDic()
# print("")
#
# ls("/home/")


    def writeFile(self, filename, blocks):  #pass in array of blocks as arguments

        uniqueFile = filename
        #need to find out how to make 'uniqueFile' the name of the file otherwise dictionary overwrites itself everytime method is called
        self.fileD['uniqueFile'] = blocks

        '''
        For each block from file, we need to apply replication factor 
        '''
        # For every element in blocks, part of key<uniqueFile>, Value<blocks>
        #place the block into N different datanodes either by default or updated REPLICATION
        #blockD = {blockName, datanodes}

        #return list of blocks and datanodes back to client

    # def blockReport(self, datanodeNum, blocks ):
    #     """
    #     The block report given from the data node
    #     Pass in all blocks as array assigned to the specific datanodeNumber e.g. datanode1,datanode2,etc
    #     :param datanodeNum:
    #     :param blocks:
    #     :return:
    #     """
    #     blockManager = xmlrpclib.ServerProxy('http://localhost:5000')
    #     print blockManager.get_blockID()
    #     print blockManager.get_DataNodeNumber()



######### Alex's fault tolerance stuff #########

    #start threads
    def startThreads(self):
        start_new_thread(self.checkTimes, ())

    def checkTimes(self):
        while 1:
            time.sleep(30)
            for ip in self.alive.keys():
                diff = time.time() - self.alive[ip]
                if (diff > 40):
                    del self.alive[ip]
                    self.createNewDN(ip)
                    self.deleteFromBlockReport(ip)


    def deleteFromBlockReport(self, dnIp):
        for block in self.blockD[dnIp]:
            for ip in self.dnToBlock[block]:
                if (ip == dnIp):
                    self.dnToBlock[block].remove(dnIp)
        

    def createNewDN(self, prevDNIp):
        ec2 = boto3.resource('ec2')
        instance_id = ''
        instance_check = None
        instance = ec2.create_instances(
        ImageId = 'ami-2c019654',
        MinCount = 1,
        MaxCount = 1,
        InstanceType='t2.micro',
        )
        instance_id = instance[0].id
        print('Created Datanode Server:', instance[0].id, instance[0].public_ip_address)
        instance_check = instance[0]
        print('Getting Public IP...')

        # Wait for server to
        while instance_check.public_ip_address == None:
            time.sleep(10)
            instance_check = ec2.Instance(instance_id)

        dnIp = str(instance_check.public_ip_address)
        datanode = xmlrpclib.ServerProxy("http://" + dnIp + ':' + '8888')
        datanode.receiveNNIp("http://" + self.ip, "http://" + dnIp)
        self.moveBlocks(dnIp, prevDNIp)


    def moveBlocks(self, targetDNIp, prevDNIp):
        for block in self.blockD[prevDNIp]:
            for ip in self.dnToBlock[block]:
                try:
                    datanode = dnRPCClient.dnRPCClient(ip, 8888)
                    success = datanode.targetBlock(block, targetDNIp)
                    if (success):
                        break
                except:
                    continue
        return True

# for testing
# s = Namenode()
# s.blockReport( 1, 2)
