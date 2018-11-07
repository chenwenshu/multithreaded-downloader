import os
import pickle
import socket
import threading
import time

import click

from glob import glob
from shutil import copyfileobj


class ClientSession(object):
    # noinspection PyShadowingNames
    def __init__(self, client_name, client_udp_port, server_name, server_tcp_port, filename, num_threads):
        # initialize variables
        self.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_name = client_name
        self.client_udp_port = int(client_udp_port)
        self.server_name = server_name
        self.server_tcp_port = server_tcp_port
        self.filename = filename
        self.num_threads = str(num_threads)
        self.initialize_connection()
    
    def close_connection(self):
        self.client_tcp_socket.close()
    
    def initialize_connection(self):
        # setup 3-way handshake
        self.client_tcp_socket.connect((self.server_name, self.server_tcp_port))
        print("Client: Successfully connected to server")

        self.client_tcp_socket.send(pickle.dumps((self.num_threads, self.filename)))
        print('Client: Download will be in {} threads'.format(self.num_threads))
    
    def receive_data(self):
        # start downloading
        self.do_threading()
        self.combine_segments()
    
    def do_threading(self):
        for i in range(int(self.num_threads)):
            thread = threading.Thread(target = self.request_segment,
                                      kwargs = {'thread_num': i + 1})
            
            thread.setDaemon(True)
            thread.start()
        
        main_thread = threading.current_thread()
        
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            
            thread.join()
    
    def request_segment(self, thread_num):
        name, ext = os.path.splitext(self.filename)
        segment_name = "{0}_{1}{2}".format(name, thread_num, ext)
        
        thread_tcp_socket, thread_udp_socket = self.connect_thread_sockets(thread_num)

        time.sleep(.1)
        thread_tcp_socket.send(segment_name.encode('utf-8'))
        print('File requesting {}'.format(segment_name))
        
        # receive the segment size
        blocks = int(thread_tcp_socket.recv(1024).decode('utf-8'))
        if blocks == 0:
            print("Client: File does not exist. Please try again :(")
        
        print("Client: Thread {} receiving data...".format(thread_num))
        thread_tcp_socket.setblocking(False)
        thread_udp_socket.settimeout(.001)
        
        start_time = time.time()
        packet_loss = 0
        transmission_count = 0
        segment_id_list = []
        bytes_array = b''
        
        while True:
            while True:
                try:
                    if thread_tcp_socket.recv(1024).decode('utf-8') == 'DONE':
                        transmission_count += 1
                        # print("Client: Transmission on thread {} done..".format(thread_num))
                        break
                except socket.error:
                    pass
                    
                try:
                    data, addr = thread_udp_socket.recvfrom(1026)
                    segment_id_list.append(int.from_bytes(data[0:2], byteorder = 'big'))
                    # print('segment received {}'.format(segment_id_list))
                    bytes_array += data[2:]
                except socket.error:
                    pass
            
            missing = self.missing_elements(sorted(segment_id_list), 0, blocks - 1)
            # print("Client: Missing packets:", missing)
            if len(missing) == 0:
                print("Client: Segment is fully received on thread {}. Yay!".format(thread_num))
                thread_tcp_socket.close()
                thread_udp_socket.close()
                
                break
            
            else:
                packet_loss += len(missing)
                missing_bytes = b''
                
                for idx in missing:
                    missing_bytes += idx.to_bytes(2, byteorder = 'big')
                
                thread_tcp_socket.send(missing_bytes)
        
        end_time = time.time()
        self.assemble_data(segment_id_list, segment_name, bytes_array)
        
        print("***************************************")
        print("Total time taken: {}s".format(round(end_time - start_time, 5)))
        print("Percentage packet loss: {}%".format(round(packet_loss / (blocks * transmission_count), 10) * 100))
        print("***************************************")
    
    def connect_thread_sockets(self, thread_num):
        # send over information about TCP socket
        self.client_tcp_socket.send((str(self.server_tcp_port + thread_num) + '\n').encode('utf-8'))
        
        # thread_num is (i + 1)
        thread_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        thread_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while True:
            try:
                time.sleep(.1)
                print('Trying to connect to port {}'.format((self.server_name, self.server_tcp_port + thread_num)))
                thread_tcp_socket.connect((self.server_name, self.server_tcp_port + thread_num))
                break
                
            except socket.error as e:
                print('error {}'.format(e))

        # send over information about UDP socket
        thread_tcp_socket.send(pickle.dumps((self.client_name, self.client_udp_port + thread_num)))

        thread_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        thread_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        thread_udp_socket.bind((self.client_name, self.client_udp_port + thread_num))
        print('udp port {}'.format(self.client_udp_port + thread_num))
        
        return thread_tcp_socket, thread_udp_socket
    
    def combine_segments(self):
        name, ext = os.path.splitext(self.filename)
        file_list = sorted(glob(name + '*_copy' + ext))
        
        with open('download_' + self.filename, 'a+b') as whole_file:
            for partial in file_list:
                partial_file = open(partial, 'r+b')
                copyfileobj(partial_file, whole_file)
                partial_file.close()
            
            whole_file.close()
        
        print('Successfully combined file {}'.format(self.filename))
        return
    
    @staticmethod
    def assemble_data(segment_id_list, segment_name, bytes_array):
        sorted_segment_id_list = sorted(enumerate(segment_id_list), key = lambda x: x[1])
        split_filename = os.path.splitext(segment_name)
        new_filename = split_filename[0] + '_copy' + split_filename[1]
        with open(new_filename, 'wb') as f:
            for original, correct in sorted_segment_id_list:
                f.write(bytes_array[original * 1024:(original + 1) * 1024])
        # print("Client: File is successfully downloaded")
    
    @staticmethod
    def missing_elements(l, start, end):
        return sorted(set(range(start, end + 1)).difference(l))


@click.command()
@click.option('-c', '--client-name', help = 'Client Name', required = True)
@click.option('--client-udp-port', help = 'Client UDP Port', default = 50000)
@click.option('-s', '--server-name', help = 'Server Name', required = True)
@click.option('--server-tcp-port', help = 'Server TCP Port', default = 12001)
@click.option('-f', '--filename', help = 'File to Download', required = True)
@click.option('-t', '--num-threads', help = 'Number of Threads', default = 4)
def start_client(client_name, client_udp_port, server_name, server_tcp_port, filename, num_threads):
    client_session = ClientSession(client_name, client_udp_port, server_name, server_tcp_port, filename, num_threads)
    
    client_session.receive_data()
    client_session.close_connection()


if __name__ == '__main__':
    start_client()