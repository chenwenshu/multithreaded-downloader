import math
import os
import pickle
import socket
import sys
import threading
import time


class MainServerSession(object):
    def __init__(self, server_name, server_tcp_port, trans_rate):
        self.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_name = server_name
        self.server_tcp_port = server_tcp_port
        self.trans_rate = trans_rate
        self.current_server_udp_port = 50000  # for keeping track of UDP port number
        self.initialize_connection()
    
    def initialize_connection(self):
        # wait for TCP connection from client
        self.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allow reuse of port number
        self.server_tcp_socket.bind((self.server_name, self.server_tcp_port))
        self.server_tcp_socket.listen(1)
        print('Server: Listening for connections')
        
        # TODO: server listens to num_threads and split the file
        # create a new thread when there is incoming connections
        while True:
            connection_tcp_socket, addr = self.server_tcp_socket.accept()
            a = ThreadedServerSession(self.server_name, self.current_server_udp_port, self.trans_rate,
                                      connection_tcp_socket)
            threading.Thread(target = a.send_data).start()
            self.current_server_udp_port += 1
            print("Server: Connection accepted")
    
    def close_connection(self):
        self.server_tcp_socket.close()


class ThreadedServerSession(object):
    def __init__(self, server_name, server_udp_port, trans_rate, connection_tcp_socket):
        self.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_name = server_name
        self.server_udp_port = server_udp_port
        self.buffer_size = 1024
        # to account for transmission time
        self.sleep_time = 1 / ((float(trans_rate) * 1000000 / 8) / (self.buffer_size + 2))  # without transmission time
        self.connection_tcp_socket = connection_tcp_socket
        self.client_name = ''
        self.client_udp_port = 0
        self.filename = ''
    
    def close_connection(self):
        print('Closing thread connection')
        self.server_udp_socket.close()
        self.connection_tcp_socket.close()
    
    def send_data(self):
        print("Sleep time", self.sleep_time)
        
        # start a UDP session to send packets over
        client_addr = self.connection_tcp_socket.recv(1024)
        self.client_name, self.client_udp_port = pickle.loads(client_addr)
        self.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_udp_socket.bind((self.server_name, self.server_udp_port))
        
        print("Server: Awaiting filename from client")
        while True:
            self.filename = self.connection_tcp_socket.recv(1024)
            # check whether file exists in current directory
            if os.path.isfile(self.filename):
                file_size = os.path.getsize(self.filename)
                blocks = math.ceil(file_size / 1024)
                self.connection_tcp_socket.send(str(blocks).encode('utf-8'))
                break
            
            else:
                self.connection_tcp_socket.send('0'.encode('utf-8'))
                print("Server: File does not exist. Continue waiting for filename")
        
        with open(self.filename, 'rb') as f:
            print("Server: Sending data over...")
            bytes_array = b''  # a bytearray for temporary storage of bytes from file for retrieval
            data = f.read(self.buffer_size)
            segment_id = 0  # use 16 bits to range from 0 to 65535
            while data:
                segment_id_bytes = segment_id.to_bytes(2, byteorder = 'big')
                data = segment_id_bytes + data  # sending over 2 bytes of segment id + 1024 bytes of data
                bytes_array += data  # this code shows a substantial increase in time taken
                
                self.server_udp_socket.sendto(data, (self.client_name,
                                                     self.client_udp_port))
                # this code shows a substantial increase in time taken. might be due to client side taking time as well
                
                time.sleep(self.sleep_time)
                data = f.read(self.buffer_size)
                segment_id += 1
            
            while True:
                # once done, send a DONE signal and wait for next message
                self.connection_tcp_socket.send('DONE'.encode('utf-8'))
                missing_bytes = self.connection_tcp_socket.recv(1024)
                missing = [int.from_bytes(missing_bytes[i:i + 2], byteorder = 'big') for i in
                           range(0, len(missing_bytes), 2)]
                
                if len(missing) == 0:
                    break
                else:
                    for idx in missing:
                        self.server_udp_socket.sendto(bytes_array[idx * 1026:(idx + 1) * 1026],
                                                      (self.client_name, self.client_udp_port))
                        time.sleep(self.sleep_time)
        
        self.close_connection()


if __name__ == '__main__':
    serverName = sys.argv[1]
    server_TCPPort = 12001
    transrate = sys.argv[2]  # user-defined rate in megabits per second (Mbps)
    mainServerSession = MainServerSession(serverName, server_TCPPort, transrate)
    mainServerSession.close_connection()
