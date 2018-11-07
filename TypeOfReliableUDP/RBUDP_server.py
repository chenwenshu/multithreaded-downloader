import socket
import time
import sys
import os
import math
import pickle
import threading

class MainServerSession:
    def __init__(self, serverName, server_TCPPort, transrate):
        self.serverName = serverName
        self.server_TCPPort = server_TCPPort
        self.transrate = transrate
        self.current_server_UDPPort = 50000 # for keeping track of UDP port number
        self.initializeConnection()

    def initializeConnection(self):
        # wait for TCP connection from client
        self.server_TCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          # allow reuse of port number
        self.server_TCPSocket.bind((self.serverName, self.server_TCPPort))
        self.server_TCPSocket.listen(1)
        print('Server: Listening for connections')
        # create a new thread when there is incoming connections
        while True:
            connection_TCPSocket, addr = self.server_TCPSocket.accept()
            a = ThreadedServerSession(self.serverName, self.current_server_UDPPort, self.transrate, connection_TCPSocket)
            threading.Thread(target=a.sendData).start()
            self.current_server_UDPPort+=1
            print("Server: Connection accepted")
    def closeConnection(self):
        self.server_TCPSocket.close()
    
    # TODO: closing a thread

class ThreadedServerSession:
    def __init__(self, serverName, server_UDPPort, transrate, connection_TCPSocket):
        self.serverName = serverName
        self.server_UDPPort = server_UDPPort
        # self.server_TCPPort = server_TCPPort
        self.buffer_size = 1024
        # self.sleeptime = 1/((float(transrate)*1000000/8)/(self.buffer_size+2)) + 0.0001 # 0.0001 to account for transmission time
        self.sleeptime = 1/((float(transrate)*1000000/8)/(self.buffer_size+2)) # without transmission time
        self.connection_TCPSocket = connection_TCPSocket
        # self.initializeConnection()

    # def initializeConnection(self):
    #     # wait for TCP connection from client
    #     self.server_TCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self.server_TCPSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allow reuse of port number
    #     self.server_TCPSocket.bind((self.serverName, self.server_TCPPort))
    #     self.server_TCPSocket.listen(1)
    #     print('Server: Listening for connections')
        
    #     while True:
    #         # TODO: server only able to accept one incoming connection. need to create multiple connections with multithreading
    #         self.connection_TCPSocket, addr = self.server_TCPSocket.accept()
    #         print("Server: Connection accepted")
    #         # self.clientName = self.connection_TCPSocket.recv(1024)
    #         # self.clientName = self.clientName.decode('utf-8')
    #         # self.client_UDPPort = self.connection_TCPSocket.recv(1024)
    #         # self.client_UDPPort = int(self.client_UDPPort.decode('utf-8'))
    #         clientaddr = self.connection_TCPSocket.recv(1024)
    #         self.clientName, self.client_UDPPort = pickle.loads(clientaddr)

    #         # send over number of blocks
    #         # self.filename = 'test2.JPG' # TODO: to be changed
    #         # filesize = os.path.getsize(self.filename)
    #         # blocks = math.ceil(filesize/1024)
    #         # self.connection_TCPSocket.send(str(blocks).encode('utf-8'))

    #         # TODO: start a UDP session to send packets over
    #         self.server_UDPSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #         self.server_UDPSocket.bind((serverName, server_UDPPort))
    #         break
    
    def closeConnection(self):
        print('Closing thread connection')
        self.server_UDPSocket.close()
        self.connection_TCPSocket.close()

    def sendData(self):
        print("Sleep time",self.sleeptime)

        # start a UDP session to send packets over
        clientaddr = self.connection_TCPSocket.recv(1024)
        self.clientName, self.client_UDPPort = pickle.loads(clientaddr)
        self.server_UDPSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_UDPSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_UDPSocket.bind((self.serverName, self.server_UDPPort))

        print("Server: Awaiting filename from client")
        while True:
            self.filename = self.connection_TCPSocket.recv(1024)
            # check whether file exists in current directory
            if os.path.isfile(self.filename):
                filesize = os.path.getsize(self.filename)
                blocks = math.ceil(filesize/1024)
                self.connection_TCPSocket.send(str(blocks).encode('utf-8'))
                break
            else:
                self.connection_TCPSocket.send('0'.encode('utf-8'))
                print("Server: File does not exist. Continue waiting for filename")

        with open(self.filename, 'rb') as f:
            print("Server: Sending data over...")
            bytesarray = b''   # a bytearray for temporary storage of bytes from file for retrieval
            data = f.read(self.buffer_size)
            segment_id = 0 # use 16 bits to range from 0 to 65535
            while(data):
                segment_id_bytes = segment_id.to_bytes(2,byteorder='big')
                data = segment_id_bytes + data  # sending over 2 bytes of segment id + 1024 bytes of data 
                bytesarray += data # this code shows a substantial increase in time taken 
                #starttime = time.time()
                self.server_UDPSocket.sendto(data, (self.clientName, self.client_UDPPort)) # this code shows a subtantial increase in time taken. might be due to client side taking time as well
                #if segment_id%100==0:
                #    print("Time taken for 1 transmission: {}".format(time.time()-starttime))
                time.sleep(self.sleeptime)
                data = f.read(self.buffer_size)
                segment_id+=1
            
            while True:
                # once done, send a DONE signal and wait for next message
                self.connection_TCPSocket.send('DONE'.encode('utf-8'))
                missingbytes = self.connection_TCPSocket.recv(1024)
                missing = [int.from_bytes(missingbytes[i:i+2], byteorder='big') for i in range(0,len(missingbytes),2)]

                if len(missing)==0:
                    break
                else:
                    for idx in missing:
                        self.server_UDPSocket.sendto(bytesarray[idx*1026:(idx+1)*1026], (self.clientName, self.client_UDPPort))
                        time.sleep(self.sleeptime)
        
        self.closeConnection()

if __name__=='__main__':
    serverName = sys.argv[1]
    server_TCPPort = 12001
    transrate = sys.argv[2] # user-defined rate in megabits per second (Mbps)
    mainServerSession = MainServerSession(serverName, server_TCPPort, transrate)
    mainServerSession.sendData()
    mainServerSession.closeConnection()





