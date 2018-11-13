import socket
import os

TCP_IP = "127.0.0.1"
FILE_PORT = 50123
DATA_PORT = 50234
timeout = 3
buf = 1024


sock_f = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_f.bind((TCP_IP, FILE_PORT))
sock_f.listen(1)

sock_d = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_d.bind((TCP_IP, DATA_PORT))
sock_d.listen(1)


while True:
    conn, addr = sock_f.accept()
    data = conn.recv(buf)
    data = data.decode('utf-8')
    if data:
        print ("File name:", data)
        file_name = data.strip()
    split_filename = os.path.splitext(file_name)
    f = open(split_filename[0]+'_copy'+split_filename[1], 'wb')

    conn, addr = sock_d.accept()
    while True:
        data = conn.recv(buf)
        if not data:
            break
        f.write(data)

    print( "%s Finish!" % file_name)
    f.close()