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
    """The main session running on the client side"""
    
    # noinspection PyShadowingNames
    def __init__(self, client_name, client_udp_port, server_name, server_tcp_port, filename, num_threads):
        """
        :param client_name: IP address of the client
        :param client_udp_port: starting UDP port number of the client receiving data
        :param server_name: IP address of the server
        :param server_tcp_port: TCP port number of the server listening to clients' connections
        :param filename: name of the file requested by the client
        :param num_threads: number of threads intended to use
        """
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
        """Initializes TCP connects with the server and communicates necessary information"""
        # setup 3-way handshake with the main server session
        self.client_tcp_socket.connect((self.server_name, self.server_tcp_port))
        print("Client: Successfully connected to server")
        
        # send over the number of threads and filename to the main server session
        self.client_tcp_socket.send(pickle.dumps((self.num_threads, self.filename)))
        print('Client: Download will be in {} threads'.format(self.num_threads))
        
        # receives the server TCP port number exclusively created for this client session
        self.new_server_tcp_port = pickle.loads(self.client_tcp_socket.recv(1024))
        
        # receives the checksum of the original file from the server side
        self.server_md5 = self.client_tcp_socket.recv(1024)
    
    def receive_data(self):
        """The main method handling the download session on client side"""
        self.do_threading()
        self.combine_segments()
        
        print('\n' * (int(self.num_threads) - 1))   # avoid line conflict with thread-level pbars
        print('File passes checksum!' if self.is_correct() else 'File is corrupted!')
    
    def do_threading(self):
        """Creates and ends all threads"""
        # a Lock object is used to prevent mixed up printing on different threads
        lock = threading.Lock()
        
        # create threads
        for i in range(int(self.num_threads)):
            thread = ThreadedClientSession(self.client_name, self.client_udp_port,
                                           self.server_name, self.new_server_tcp_port,
                                           self.filename, lock)
            
            t = threading.Thread(target = thread.request_segment,
                                 kwargs = {'thread_num': i + 1})
            
            t.setDaemon(True)
            t.start()
        
        main_thread = threading.current_thread()
        
        # end threads
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            
            thread.join()
    
    def combine_segments(self):
        """Combines the thread-downloaded segments in the correct sequence to get the whole file"""
        name, ext = os.path.splitext(self.filename)
        
        # sort the downloaded segments according to the sequence number
        file_list = sorted(glob(name + '*_copy' + ext), key = lambda x: int(x.split('_')[-2]))
        
        with open('download_' + self.filename, 'wb') as whole_file:
            # write the segment into the whole file
            for partial in file_list:
                partial_file = open(partial, 'r+b')
                copyfileobj(partial_file, whole_file)
                partial_file.close()
        
        # clean up the segments
        [os.remove(segment) for segment in file_list]
        return

    def is_correct(self):
        """Implements a MD5 checksum on the client's whole file and compares against the server's"""
        client_md5 = hashlib.md5()
    
        with open('download_' + self.filename, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                client_md5.update(chunk)
    
        return self.server_md5 == client_md5.digest()
    

class ThreadedClientSession(object):
    """The thread session for actual downloading"""
    
    def __init__(self, client_name, client_udp_port, server_name, new_server_tcp_port, filename, lock):
        """
        :param client_name: IP address of the client
        :param client_udp_port: UDP port number of the client's thread receiving data
        :param server_name: IP address of the server
        :param new_server_tcp_port: TCP port number of the server connected to this client
        :param filename: name of the file segment requested by the thread
        :param lock: Lock object controlling printing behaviour
        """
        self.client_name = client_name
        self.client_udp_port = client_udp_port
        self.server_name = server_name
        self.new_server_tcp_port = new_server_tcp_port
        self.filename = filename
        self.lock = lock
    
    def request_segment(self, thread_num):
        """
        Downloads the segment from the server
        
        :param thread_num: ID of this thread
        """
        name, ext = os.path.splitext(self.filename)
        
        # name of the segment requested by this thread
        segment_name = "{0}_{1}{2}".format(name, thread_num, ext)
        # name of the segment saved on the client
        saved_name = os.path.splitext(segment_name)[0] + '_copy' + os.path.splitext(segment_name)[1]
        
        # initialize thread-level connection
        thread_tcp_socket, thread_udp_socket = self.connect_thread_sockets(thread_num)
        
        # wait to establish the connection
        time.sleep(.1)
        # send over the segment name
        thread_tcp_socket.send(segment_name.encode('utf-8'))
        
        # receive the segment size in Kb
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
                        # check if the transmission is done
                        if thread_tcp_socket.recv(1024).decode('utf-8') == 'DONE':
                            transmission_count += 1
                            break
                    
                    except socket.error:
                        # if not done, continue with the UDP transmission
                        pass
                    
                    try:
                        # receive and save the packets
                        data, _ = thread_udp_socket.recvfrom(1026)
                        segment_id_list = self.save_packet(segment_file, data, segment_id_list)
                        
                        pbar.update(1)
                    except socket.error:
                        pass
                
                # check for missing packets
                missing = self.missing_elements(sorted(segment_id_list), 0, blocks - 1)
                
                # terminates the download process if all packets are received
                if len(missing) == 0:
                    break
                
                else:
                    packet_loss += len(missing)
                    missing_bytes = b''
                    
                    for idx in missing:
                        missing_bytes += idx.to_bytes(2, byteorder = 'big')
                    
                    # send over the ID of the missing packets
                    thread_tcp_socket.send(missing_bytes)
        
        segment_file.close()
    
    def connect_thread_sockets(self, thread_num):
        """Establishes TCP and UDP connections with the server on a thread level"""
        thread_tcp_port = (self.server_name, self.new_server_tcp_port)
        
        # thread_num is (i + 1)
        thread_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        thread_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while True:
            try:
                thread_tcp_socket.connect(thread_tcp_port)
                break
            
            except socket.error as e:
                print('{}\nwhen thread {} tries to connect to server'.format(e, thread_num))
        
        # send over information about UDP socket
        thread_tcp_socket.send(pickle.dumps((self.client_name, self.client_udp_port + thread_num)))
        
        # establishes UDP connection
        thread_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        thread_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        thread_udp_socket.bind((self.client_name, self.client_udp_port + thread_num))
        
        return thread_tcp_socket, thread_udp_socket
    
    @staticmethod
    def show_summary(thread_num, start_time, end_time, packet_loss, blocks, transmission_count):
        """Prints summary of the download status"""
        tqdm.write("***************************************")
        tqdm.write("Summary on Thread {}".format(thread_num))
        tqdm.write("Total time taken: {}s".format(round(end_time - start_time, 5)))
        tqdm.write("Percentage packet loss: {}%".format(round(packet_loss / (blocks * transmission_count), 10) * 100))
        tqdm.write("***************************************")
    
    @staticmethod
    def save_packet(file, segment, segment_id_list):
        """Saves the received packets onto the storage instantly to prevent memory hogging"""
        segment_id = int.from_bytes(segment[:2], byteorder = 'big')
        
        # prevent repetitive writing
        if segment_id not in segment_id_list:
            # keep track of the received packets
            segment_id_list.append(segment_id)
            
            # offsets the previous packets
            file.seek(segment_id * 1024)
            file.write(segment[2:])
        
        return segment_id_list
    
    @staticmethod
    def missing_elements(id_list, start, end):
        """
        Returns segment ID of the missing packets
        
        :param id_list: list of segment ID received
        :param start: ID of the first segment
        :param end: ID of the last segment
        :return: sorted list of missing packets
        """
        return sorted(set(range(start, end + 1)).difference(id_list))


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
