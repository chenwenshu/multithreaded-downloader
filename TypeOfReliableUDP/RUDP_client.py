import socket
import hashlib
import os
import sys


def RUDPClient(serverAddress, serverPort, filename):
    # Delimiter
    delimiter = "|:|:|";

    # Start - Connection initiation
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10);
    server_address = (serverAddress, serverPort)
    seqNoFlag = 0
    f = open("r_" + filename, 'w');

    try:
        # Connection trials
        connection_trials_count=0
        # Send data
        print  ('Requesting %s' % filename)
        sent = sock.sendto(filename.encode('utf-8'), server_address)
        # Receive indefinitely
        while 1:
            # Receive response
            print  ('\nWaiting to receive..')
            try:
                data, server = sock.recvfrom(4096)
                # Reset failed trials on successful transmission
                connection_trials_count=0;
            except:
                connection_trials_count += 1
                if connection_trials_count < 5:
                    print ("\nConnection time out, retrying")
                    continue
                else:
                    print ("\nMaximum connection trials reached, skipping request\n")
                    os.remove("r_" + filename)
                    break
            # Understanding packet 
            string_data = data.decode('utf-8')
            seqNo = string_data.split(delimiter)[1]
            sendback = string_data.split(delimiter)[3]
            sendback = sendback.encode('utf-8')
            clientHash = hashlib.sha1(sendback).hexdigest()
            print ("Server hash: " + string_data.split(delimiter)[0])
            print ("Client hash: " + clientHash)
            # Check if corrupted and correct sequence
            if string_data.split(delimiter)[0] == clientHash and seqNoFlag == int(seqNo == True):
                packetLength = string_data.split(delimiter)[2]
                if string_data.split(delimiter)[3] == "FNF":
                    # if file not found 
                    print ("Requested file could not be found on the server")
                    os.remove("r_" + userInput)
                else:
                    f.write(string_data.split(delimiter)[3]);
                print ("Sequence number: %s\nLength: %s" % (seqNo, packetLength))
                print ("Server: %s on port %s" % server)
                tosend = str(seqNo) + "," + packetLength
                tosend = tosend.encode('utf-8')
                sent = sock.sendto(tosend, server)
            else:
                print ("Checksum mismatch detected, dropping packet")
                print ("Server: %s on port %s" % server)
                continue;
            if int(packetLength) < 500:
                seqNo = int(not seqNo)
                break
    except KeyboardInterrupt:
        print("Keyboard Interrupt Detected")
    finally:
        print ("Closing socket")
        sock.close()
        f.close()

if __name__ == "__main__":
    # Set address and port
    serverAddress = sys.argv[1]
    serverPort = int(sys.argv[2])
    filename = sys.argv[3]
    print("Server Address : " + serverAddress + "\nServer Port : "+ str(serverPort) +"\n")
    RUDPClient(serverAddress, serverPort, filename)
