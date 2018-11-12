import os
import pickle
import socket
import threading
import time

import click

from math import ceil

from fsplit.filesplit import FileSplit


class MainServerSession(object):
    def __init__(self, server_name, server_tcp_port, trans_rate):
        self.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_name = server_name
        self.server_tcp_port = server_tcp_port
        self.trans_rate = trans_rate
        self.num_threads = 0
        self.filename = ''
    
    def initialize_connection(self):
        # wait for TCP connection from client
        self.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allow reuse of port numbers
        self.server_tcp_socket.bind((self.server_name, self.server_tcp_port))
        self.server_tcp_socket.listen(1)
        print('Server: Listening for connections')
        
        server_tcp_connection, addr = self.server_tcp_socket.accept()
        
        client_info = server_tcp_connection.recv(1024)
        self.num_threads, self.filename = pickle.loads(client_info)
        self.num_threads = int(self.num_threads)
        
        print('Server: File {0} is requested by Client {1} with {2} threads.'
              .format(self.filename, addr, self.num_threads))
        
        self.segment_file()
        thread_count = 0
        
        # tcp_port_list = server_tcp_connection.recv(1024).decode('utf-8').split()
        
        while thread_count < self.num_threads:
            thread_tcp_connection, thread_tcp_addr = server_tcp_connection.accept()
            thread = ThreadedServerSession(self.server_name, self.trans_rate, thread_tcp_connection)
            
            print('Thread {} running'.format(thread_count + 1))
            thread_count += 1
            
            t = threading.Thread(target = thread.send_data)
            t.setDaemon(True)
            t.start()
            
            print('Server: Connection accepted')
            
        main_thread = threading.current_thread()
        
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            
            thread.join()
    
    def close_connection(self):
        self.server_tcp_socket.close()
    
    def segment_file(self):
        if not os.path.exists('./temp'):
            os.mkdir('./temp')
        
        file_size = int(os.stat(self.filename).st_size)
        chunk_size = ceil(file_size / self.num_threads)
        
        fs = FileSplit(self.filename, chunk_size, './temp')
        fs.split()
        
        name, ext = os.path.splitext(self.filename)
        second_last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, self.num_threads, ext))
        last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, self.num_threads + 1, ext))
        
        # To get rid of the trailing file
        with open(second_last_filename, 'a+b') as f:
            last_file = open(last_filename, 'r+b')
            tail = last_file.read()
            last_file.close()
            
            f.write(tail)
            f.close()
        
        os.remove(last_filename)
        
        return


class ThreadedServerSession(object):
    def __init__(self, server_name, trans_rate, thread_tcp_connection):
        self.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.server_name = server_name
        self.buffer_size = 1024
        # to account for transmission time
        self.sleep_time = 1 / ((float(trans_rate) * 1000000 / 8) / (self.buffer_size + 2))  # without transmission time
        self.client_name = ''
        self.client_udp_port = 0
        self.filename = ''
        self.thread_tcp_connection = thread_tcp_connection
    
    def close_connection(self):
        print('Closing thread connection')
        self.server_udp_socket.close()
        self.thread_tcp_connection.close()
    
    def send_data(self):
        print("Sleep time", self.sleep_time)
        
        # start a UDP session to send packets over
        client_addr = self.thread_tcp_connection.recv(1024)
        self.client_name, self.client_udp_port = pickle.loads(client_addr)
        
        print("Server: Awaiting filename from client")
        while True:
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
            bytes_array = b''  # a byte array for temporary storage of bytes from file for retrieval
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
                self.thread_tcp_connection.send('DONE'.encode('utf-8'))
                missing_bytes = self.thread_tcp_connection.recv(1024)
                missing = [int.from_bytes(missing_bytes[i: i + 2], byteorder = 'big') for i in
                           range(0, len(missing_bytes), 2)]
                
                if len(missing) == 0:
                    break
                else:
                    for idx in missing:
                        self.server_udp_socket.sendto(bytes_array[idx * 1026:(idx + 1) * 1026],
                                                      (self.client_name, self.client_udp_port))
                        time.sleep(self.sleep_time)
        
        self.close_connection()


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
