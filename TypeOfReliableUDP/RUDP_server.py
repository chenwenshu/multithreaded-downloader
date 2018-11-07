import socket
import threading
import hashlib
import time
import datetime
import random
import sys


# Packet class definition
class packet():
    checksum = 0;
    length = 0;
    seqNo = 0;
    msg = 0;

    def make(self, data):
        self.msg = data
        self.length = str(len(data))
        self.checksum=hashlib.sha1(data.encode('utf-8')).hexdigest()
        print ("Length: %s\nSequence number: %s" %(self.length, self.seqNo))


# Connection handler
def handleConnection(address, data):
    # Delimiter
    delimiter = "|:|:|";

    # Seq number flag
    seqFlag = 0

    packet_count=0
    time.sleep(0.5)
    start_time=time.time()
    print ("Request started at: " + str(datetime.datetime.utcnow()))
    pkt = packet()
    threadSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    startTime=time.time()

    # Check if file is valid 
    try:
        print ("Opening file %s" % data)
        fileName = data.decode('utf-8')
        fileRead = open(fileName, 'r')
        data = fileRead.read()
        fileRead.close()
    except:
        msg="FNF";
        pkt.make(msg);
        finalPacket = str(pkt.checksum) + delimiter + str(pkt.seqNo) + delimiter + str(pkt.length) + delimiter + pkt.msg
        threadSock.sendto(finalPacket, address)
        print ("Requested file could not be found, replied with FNF")
        return

    
    # Fragment and send file 500 byte by 500 byte
    x = 0
    expectedPacket = (int((len(data) / 500) + 1))
    while (x < int((len(data) / 500) + 1)):
        packet_count += 1
        msg = data[x * 500:x * 500 + 500];
        pkt.make(msg);
        finalPacket = str(pkt.checksum) + delimiter + str(pkt.seqNo) + delimiter + str(pkt.length) + delimiter + pkt.msg

        # Send packet
        sent = threadSock.sendto(finalPacket.encode('utf-8'), address)
        print  ('Sent %s bytes back to %s, awaiting acknowledgment..' % (sent, address))
        threadSock.settimeout(2)
        try:
            ack, address = threadSock.recvfrom(100);
            ack = ack.decode('utf-8')
        except:
            # else after timeout, resend 
            print ("Time out reached, resending ...%s" % x)
            continue;
        # Check if acknowledgement is sent; ^
        if ack.split(",")[0] == str(pkt.seqNo):
            pkt.seqNo = int(not pkt.seqNo)
            print ("Acknowledged by: " + ack + "\nAcknowledged at: " + str(datetime.datetime.utcnow()) + "\nElapsed: " + str(time.time() - start_time))
            x += 1
    endTime=time.time()
    print("\nDone in within : " + str(endTime-startTime))
    packetLoss = expectedPacket - packet_count
    print("Packet Loss : "+ str(packetLoss))
##    except Exception as e:
##        print(e)

def RUDPServer(serverAddress, serverPort):
    

    # Start - Connection initiation
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind the socket to the port
    server_address = (serverAddress, serverPort)
    print  ('Starting up on %s port %s' % server_address)
    sock.bind(server_address)

    # Listening for requests indefinitely
    while True:
        print  ('Waiting to receive message')
        data, address = sock.recvfrom(600)
        connectionThread = threading.Thread(target=handleConnection, args=(address, data))
        connectionThread.start()
        print  ('Received %s bytes from %s' % (len(data), address))
        
if __name__ == "__main__":
    # Set address and port
    serverAddress = sys.argv[1]
    serverPort = int(sys.argv[2])
    print("Server Address : " + serverAddress + "\nServer Port : "+ str(serverPort) +"\n")
    RUDPServer(serverAddress, serverPort)


