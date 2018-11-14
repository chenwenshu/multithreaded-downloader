import hashlib
import os
import pickle
import random
import socket
import threading
import time
from math import ceil
from shutil import rmtree
import click
from fsplit.filesplit import FileSplit

class MainServerSession(object):
    """Main Server for listening to any incoming connection"""
    def __init__(self, server_name, server_tcp_port, trans_rate):
        """
        :param server_name:ip address of server
        :param server_tcp_port:port number of tcp socket of MmainServerSession
        :param trans_rate:user-specified transfer rate
        """

        self.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_name = server_name
        self.server_tcp_port = server_tcp_port
        self.trans_rate = trans_rate
        self.num_threads = 0
        self.filename = ''
    
    def initialize_connection(self):
        """Start server and wait for tcp connection"""

        # wait for TCP connection from client
        self.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allow reuse of port numbers
        self.server_tcp_socket.bind((self.server_name, self.server_tcp_port))
        self.server_tcp_socket.listen(5)
        print('Server: Listening for connections')
        
        # keep listening for incoming connection and spawn a new master thread for handling the incoming connection
        while True:
            server_tcp_connection, addr = self.server_tcp_socket.accept()
            master = MasterThreadedServerSession(self.server_name, self.trans_rate, server_tcp_connection)
            master_thread = threading.Thread(target = master.create_master_thread)
            master_thread.setDaemon(True)
            master_thread.start()
            print("Server: New connection accepted")
        
    def close_connection(self):
        """Close any open socket"""
        self.server_tcp_socket.close()

# Master Thread for handling an incoming connection
class MasterThreadedServerSession(object):
    """Create new thread for each new file request"""

    def __init__(self, server_name, trans_rate, server_tcp_connection):
        """
        :param server_name:ip address of server_name
        :param trans_rate:user-specified transfer rate
        :param server_tcp_connection:spawned tcp socket with accepted connection
        """

        self.new_server_tcp_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_name = server_name
        self.trans_rate = trans_rate
        self.num_threads = 0
        self.filename = ''
        self.server_tcp_connection = server_tcp_connection
    
    def create_master_thread(self):
        """Start the master thread for handling incoming connection"""

        client_info = self.server_tcp_connection.recv(1024)
        self.num_threads, self.filename = pickle.loads(client_info)
        self.num_threads = int(self.num_threads)
        
        # print('Server: File {0} is requested by Client {1} with {2} threads.'
        #       .format(self.filename, self.server_name, self.num_threads))
        
        # master segments file based on number of threads
        self.segment_file()
        # create new socket for listening to incoming tcp connection from client threads 
        rand_server_tcp_port = random.randint(49152, 65535) # 49152-65535
        self.new_server_tcp_connection.bind((self.server_name, rand_server_tcp_port))
        # tell connecting client the new tcp socket to connect to
        self.server_tcp_connection.send(pickle.dumps(rand_server_tcp_port))
        self.server_tcp_connection.send(self.md5(self.filename))
        # now wait for incoming tcp connection from client threads
        self.new_server_tcp_connection.listen(5)  # backlog refers to the # of pending connections the queue will hold

        # create a new tcp socket for each incoming tcp connection and spawn a new server thread
        for thread_count in range(self.num_threads):
            thread_tcp_connection, thread_tcp_addr = self.new_server_tcp_connection.accept()
            thread = ThreadedServerSession(self.server_name, self.trans_rate, thread_tcp_connection)
            print('Thread {} running'.format(thread_count + 1))
            thread_count += 1
            t = threading.Thread(target = thread.send_data)
            t.setDaemon(True)
            t.start()

        main_thread = threading.current_thread()

        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            thread.join()
        self.server_tcp_connection.close()
        self.new_server_tcp_connection.close()

    def segment_file(self):
        """ Segment file based on number of threads"""

        if not os.path.exists('./temp'):
            os.mkdir('./temp')
        else:
            rmtree('./temp')
            os.mkdir('./temp')
    
        file_size = int(os.stat(self.filename).st_size)
        chunk_size = ceil(file_size / self.num_threads)
    
        fs = FileSplit(self.filename, chunk_size, './temp')
        fs.split()
    
        name, ext = os.path.splitext(self.filename)
        second_last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, self.num_threads, ext))
        last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, self.num_threads + 1, ext))
    
        # To get rid of the trailing file
        if os.path.exists(last_filename):
            with open(second_last_filename, 'a+b') as f:
                last_file = open(last_filename, 'r+b')
                tail = last_file.read()
                last_file.close()
            
                f.write(tail)
                f.close()
        
            os.remove(last_filename)
    
        return
    
    @staticmethod
    def md5(filename):
        """To calculate a MD5 hash for client to check integrity"""

        hash_md5 = hashlib.md5()
    
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
    
        return hash_md5.digest()

class ThreadedServerSession(object):
    """Individual threads spawned for sending file segment to client thread"""
    def __init__(self, server_name, trans_rate, thread_tcp_connection):
        """
        :param server_name:ip address of server
        :param trans_rate:user-specified transfer rate
        :param server_tcp_connection:spawned tcp socket with accepted connection
        """

        self.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_name = server_name
        self.buffer_size = 1024
        # sleep_time is calculated based on user-specified transfer rate
        self.sleep_time = 1 / ((float(trans_rate) * 1000000 / 8) / (self.buffer_size + 2))  # without transmission time
        self.client_name = ''
        self.client_udp_port = 0
        self.filename = ''
        self.thread_tcp_connection = thread_tcp_connection
    
    def close_connection(self):
        """Close any open sockets"""
        print('Closing thread connection')
        self.server_udp_socket.close()
        # self.thread_tcp_connection.close()
    
    def send_data(self):
        """Main function for sending data for client"""
        # receive client udp port number
        client_addr = self.thread_tcp_connection.recv(1024)
        self.client_name, self.client_udp_port = pickle.loads(client_addr)
        print("Server: Awaiting filename from client")
        while True:
            # receive requested file name
            self.filename = self.thread_tcp_connection.recv(1024).decode('utf-8')
            self.filename = 'temp/' + self.filename
            print('File requested {}'.format(self.filename))

            # check whether file exists in current directory
            if os.path.isfile(self.filename):
                file_size = os.path.getsize(self.filename)
                blocks = ceil(file_size / 1024)
                self.thread_tcp_connection.send(str(blocks).encode('utf-8'))
                break
            else:
                self.thread_tcp_connection.send('0'.encode('utf-8'))
                print("Server: File does not exist. Continue waiting for filename")
        
        with open(self.filename, 'rb') as f:
            print("Server: Sending data over...")
            # for temporary storage of bytes from file for simple retrieval
            bytes_array = b''  
            data = f.read(self.buffer_size)
            segment_id = 0  # use 16bits/2bytes (0 to 65535) for segment id
            while data:
                segment_id_bytes = segment_id.to_bytes(2, byteorder = 'big')
                # sending over 2 bytes of segment id + 1024 bytes of data
                data = segment_id_bytes + data  
                bytes_array += data 
                self.server_udp_socket.sendto(data, (self.client_name, self.client_udp_port))
                # ^ this code shows a substantial increase in time taken. might be due to client side taking time as well
                time.sleep(self.sleep_time)
                data = f.read(self.buffer_size)
                segment_id += 1
            while True:
                # once done, send a DONE signal and wait for next message
                self.thread_tcp_connection.send('DONE'.encode('utf-8'))
                try:
                    # wait for id of missing segments from client
                    missing_bytes = self.thread_tcp_connection.recv(1024)
                    missing = [int.from_bytes(missing_bytes[i: i + 2], byteorder = 'big') for i in
                               range(0, len(missing_bytes), 2)]
                    if len(missing) == 0:
                        break
                    else:
                        for idx in missing:
                            # blast out missing segments to client
                            self.server_udp_socket.sendto(bytes_array[idx * 1026:(idx + 1) * 1026],
                                                          (self.client_name, self.client_udp_port))
                            time.sleep(self.sleep_time)
                except socket.error as e:
                    print(e)
        self.close_connection()

####################################################################################################################

@click.command()
@click.option('-s', '--server-name', help = 'Server IP address', required = True)
@click.option('--server-tcp-port', help = 'Server TCP Port', default = 12001)
@click.option('-r', '--trans-rate', help = 'Transmission Rate in Mbps', default = 10000.0)
def start_server(server_name, server_tcp_port, trans_rate):
    server_session = MainServerSession(server_name, server_tcp_port, trans_rate)
    server_session.initialize_connection()
    server_session.close_connection()

if __name__ == '__main__':
    start_server()
