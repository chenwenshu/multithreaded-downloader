import socket
import time
import sys
import os
import pickle
import argparse

class ClientSession:
    def __init__(self, clientName, client_UDPPort, serverName, server_TCPPort, filename=None):
        # initialize variables
        self.clientName = clientName
        self.client_UDPPort = int(client_UDPPort)
        self.serverName = serverName
        self.server_TCPPort = server_TCPPort
        self.filename = filename
        self.segmentid_list = []
        self.bytesarray = b''
        self.initializeConnection()
    
    def closeConnection(self):
        self.client_TCPSocket.close()
        self.client_UDPSocket.close()

    def initializeConnection(self):
        # create UDP socket 
        self.client_UDPSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_UDPSocket.bind((self.clientName, self.client_UDPPort))
        # create TCP socket
        self.client_TCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # setup 3-way handshake
        self.client_TCPSocket.connect((self.serverName, self.server_TCPPort))
        # send over information about UDP socket
        self.client_TCPSocket.send(pickle.dumps((self.clientName, self.client_UDPPort)))
        print("Client: Successfully connected to server")

    def receiveData(self):
        # give user option to choose file if filename not specified
        while True:
            if not self.filename:
                self.filename = input("Type filename here: ")
            # sending filename on server
            time.sleep(0.01) # give some time for server to be on recv mode
            self.client_TCPSocket.send(self.filename.encode('utf-8'))
            # get info about max file size from server
            self.blocks = int(self.client_TCPSocket.recv(1024).decode('utf-8'))
            if self.blocks != 0:
                break
            elif not self.filename:
                print("Client: File does not exist. Please try again :(")
            else:
                print("Client: Given file does not exist. Quitting...")
                exit()
        
        print("Client: Receiving data...")
        # set TCP socket to non-blocking to allow fast check for DONE signal
        self.client_TCPSocket.setblocking(False) 
        self.client_UDPSocket.settimeout(0.001)
        starttime = time.time()
        packetloss = 0
        transmissioncount = 0
        while True:
            while True:
                try:
                    if self.client_TCPSocket.recv(1024).decode('utf-8') == 'DONE':
                        transmissioncount+=1
                        print("Client: Transmission done..")
                        break
                except socket.error as e:
                    pass
                try:
                    data, addr = self.client_UDPSocket.recvfrom(1026)    
                    self.segmentid_list.append(int.from_bytes(data[0:2], byteorder='big'))
                    self.bytesarray += data[2:]
                except socket.error as e:
                    pass
            missing = self.missing_elements(sorted(self.segmentid_list), 0, self.blocks-1)
            print("Client: Missing packets:", missing)
            if len(missing)==0:
                print("Client: File is fully received. Yay!")
                break
            else:
                packetloss+=len(missing)
                missingbytes = b''
                for idx in missing:
                    missingbytes += idx.to_bytes(2,byteorder='big')
                self.client_TCPSocket.send(missingbytes)
        endtime = time.time()
        self.assembleData()
        print("***************************************")
        print("Total time taken: {}s".format(round(endtime-starttime,5)))
        print("Percentage packet loss: {}%".format(round(packetloss/(self.blocks*transmissioncount),10)*100))
        print("***************************************")
    
    def assembleData(self):
        sorted_segmentid_list = sorted(enumerate(self.segmentid_list),key=lambda x:x[1])
        split_filename = os.path.splitext(self.filename)
        new_filename = split_filename[0]+'_copy'+split_filename[1]
        with open(new_filename,'wb') as f:
            for original, correct in sorted_segmentid_list:
                f.write(self.bytesarray[original*1024:(original+1)*1024])
        print("Client: File is successfully downloaded")

    def missing_elements(self, L, start, end):
        return sorted(set(range(start, end + 1)).difference(L))

if __name__=='__main__':
    #parser = argparse.ArgumentParser(description='Arguments for client session')
    filename = None
    comd_arg = sys.argv
    clientName = sys.argv[1]
    client_UDPPort = sys.argv[2]
    serverName = sys.argv[3]
    if len(comd_arg) == 5:
        filename = sys.argv[4]
    server_TCPPort = 12001
    clientSession = ClientSession(clientName, client_UDPPort, serverName, server_TCPPort, filename)
    clientSession.receiveData()
    clientSession.closeConnection()

