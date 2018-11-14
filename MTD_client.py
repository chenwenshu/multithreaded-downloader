import hashlib
import os
import pickle
import socket
import threading
import time
from glob import glob
from shutil import copyfileobj

import click
from tqdm import tqdm


class MainClientSession(object):
    # noinspection PyShadowingNames
    def __init__(self, client_name, client_udp_port, server_name, server_tcp_port, filename, num_threads):
        # initialize variables
        self.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_name = client_name
        self.client_udp_port = int(client_udp_port)
        self.server_name = server_name
        self.server_tcp_port = server_tcp_port
        self.new_server_tcp_port = None
        self.filename = filename
        self.num_threads = str(num_threads)
        self.server_md5 = None
        self.initialize_connection()
    
    def close_connection(self):
        self.client_tcp_socket.close()
    
    def initialize_connection(self):
        # setup 3-way handshake
        self.client_tcp_socket.connect((self.server_name, self.server_tcp_port))
        print("Client: Successfully connected to server")
        
        self.client_tcp_socket.send(pickle.dumps((self.num_threads, self.filename)))
        print('Client: Download will be in {} threads'.format(self.num_threads))
        
        self.new_server_tcp_port = pickle.loads(self.client_tcp_socket.recv(1024))
        self.server_md5 = self.client_tcp_socket.recv(1024)
    
    def receive_data(self):
        # start downloading
        self.do_threading()
        self.combine_segments()
        print('\n' * (int(self.num_threads) - 1))   # avoid line conflict with thread-level pbars
        print('File passes checksum!' if self.is_correct() else 'File is corrupted!')
    
    def do_threading(self):
        lock = threading.Lock()
        
        for i in range(int(self.num_threads)):
            thread = ThreadedClientSession(self.client_name, self.client_udp_port,
                                           self.server_name, self.new_server_tcp_port,
                                           self.filename, lock)
            
            t = threading.Thread(target = thread.request_segment,
                                 kwargs = {'thread_num': i + 1})
            
            t.setDaemon(True)
            t.start()
        
        main_thread = threading.current_thread()
        
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            
            thread.join()
    
    def combine_segments(self):
        name, ext = os.path.splitext(self.filename)
        file_list = sorted(glob(name + '*_copy' + ext), key = lambda x: int(x.split('_')[-2]))
        
        with open('download_' + self.filename, 'wb') as whole_file:
            for partial in file_list:
                partial_file = open(partial, 'r+b')
                copyfileobj(partial_file, whole_file)
                partial_file.close()
            
            whole_file.close()
        
        [os.remove(segment) for segment in file_list]
        return

    def is_correct(self):
        client_md5 = hashlib.md5()
    
        with open('download_' + self.filename, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                client_md5.update(chunk)
    
        return self.server_md5 == client_md5.digest()
    

class ThreadedClientSession(object):
    def __init__(self, client_name, client_udp_port, server_name, new_server_tcp_port, filename, lock):
        self.client_name = client_name
        self.client_udp_port = client_udp_port
        self.server_name = server_name
        self.new_server_tcp_port = new_server_tcp_port
        self.filename = filename
        self.lock = lock
    
    def request_segment(self, thread_num):
        name, ext = os.path.splitext(self.filename)
        segment_name = "{0}_{1}{2}".format(name, thread_num, ext)
        saved_name = os.path.splitext(segment_name)[0] + '_copy' + os.path.splitext(segment_name)[1]
        
        thread_tcp_socket, thread_udp_socket = self.connect_thread_sockets(thread_num)
        
        time.sleep(.1)
        thread_tcp_socket.send(segment_name.encode('utf-8'))
        
        # receive the segment size
        blocks = int(thread_tcp_socket.recv(1024).decode('utf-8'))
        if blocks == 0:
            print("Client: File does not exist. Please try again :(")
        
        thread_tcp_socket.setblocking(False)
        thread_udp_socket.settimeout(.1)
        
        # start_time = time.time()
        packet_loss = 0
        transmission_count = 0
        segment_id_list = []
        segment_file = open(saved_name, 'wb')
        
        with tqdm(total = blocks, unit = 'KB', unit_scale = True, unit_divisor = 1024,
                  position = thread_num - 1) as pbar:
            while True:
                while True:
                    try:
                        if thread_tcp_socket.recv(1024).decode('utf-8') == 'DONE':
                            transmission_count += 1
                            break
                    
                    except socket.error:
                        pass
                    
                    try:
                        data, addr = thread_udp_socket.recvfrom(1026)
                        segment_id_list = self.save_packet(segment_file, data, segment_id_list)
                        
                        pbar.update(1)
                    except socket.error:
                        pass
                
                missing = self.missing_elements(sorted(segment_id_list), 0, blocks - 1)
                
                if len(missing) == 0:
                    break
                
                else:
                    packet_loss += len(missing)
                    missing_bytes = b''
                    
                    for idx in missing:
                        missing_bytes += idx.to_bytes(2, byteorder = 'big')
                    thread_tcp_socket.send(missing_bytes)
        
        segment_file.close()
        # end_time = time.time()
        
        # time.sleep(3)
        # self.lock.acquire()
        # self.show_summary(thread_num, start_time, end_time, packet_loss, blocks, transmission_count)
        # self.lock.release()
    
    def connect_thread_sockets(self, thread_num):
        # send over information about TCP socket
        
        thread_tcp_port = (self.server_name, self.new_server_tcp_port)
        
        # thread_num is (i + 1)
        thread_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        thread_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while True:
            try:
                # time.sleep(.1)
                thread_tcp_socket.connect(thread_tcp_port)
                break
            
            except socket.error as e:
                print('{}\nwhen thread {} tries to connect to server'.format(e, thread_num))
        
        # send over information about UDP socket
        thread_tcp_socket.send(pickle.dumps((self.client_name, self.client_udp_port + thread_num)))
        
        thread_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        thread_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        thread_udp_socket.bind((self.client_name, self.client_udp_port + thread_num))
        
        return thread_tcp_socket, thread_udp_socket
    
    @staticmethod
    def show_summary(thread_num, start_time, end_time, packet_loss, blocks, transmission_count):
        tqdm.write("***************************************")
        tqdm.write("Summary on Thread {}".format(thread_num))
        tqdm.write("Total time taken: {}s".format(round(end_time - start_time, 5)))
        tqdm.write("Percentage packet loss: {}%".format(round(packet_loss / (blocks * transmission_count), 10) * 100))
        tqdm.write("***************************************")
    
    @staticmethod
    def save_packet(file, segment, segment_id_list):
        segment_id = int.from_bytes(segment[:2], byteorder = 'big')
        
        if segment_id not in segment_id_list:
            segment_id_list.append(segment_id)
            
            file.seek(segment_id * 1024)
            file.write(segment[2:])
        
        return segment_id_list
    
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
    client_session = MainClientSession(client_name, client_udp_port,
                                       server_name, server_tcp_port,
                                       filename, num_threads)
    
    client_session.receive_data()
    client_session.close_connection()


if __name__ == '__main__':
    start_client()
