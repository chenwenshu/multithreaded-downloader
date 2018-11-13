import socket
import sys

TCP_IP = "127.0.0.1"
FILE_PORT = 50123
DATA_PORT = 50234
buf = 1024
file_name = sys.argv[1]
byte_file_name = file_name.encode('utf-8')


try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((TCP_IP, FILE_PORT))
    sock.send(byte_file_name)
    sock.close()

    print ("Sending %s ..." % file_name)

    f = open(file_name, "rb")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((TCP_IP, DATA_PORT))
    data = f.read()
    sock.send(data)

finally:
    sock.close()
    f.close()