import sys, logging, os
from optparse import OptionParser
import tftpy

log = logging.getLogger('tftpy')
log.setLevel(logging.INFO)


handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
default_formatter = logging.Formatter('[%(asctime)s] %(message)s')
handler.setFormatter(default_formatter)
log.addHandler(handler)

def main():
    usage=""
    parser = OptionParser(usage=usage)
    parser.add_option('-H',
                      '--host',
                      help='specify ip')
    parser.add_option('-p',
                      '--port',
                      help='specify port (default: 69)',
                      default=69)
    parser.add_option('-f',
                      '--filename',
                      help='specify file')
    parser.add_option('-D',
                      '--download',
                      help='specify file to download')
    parser.add_option('-u',
                      '--upload',
                      help='specify file to upload')
    parser.add_option('-b',
                      '--blksize',
                      help='specify packet size (default: 512)')
    parser.add_option('-o',
                      '--output',
                      help='specify output file')
    parser.add_option('-i',
                      '--input',
                      help='specify input file')
    
    parser.add_option('-l',
                      '--localip',
                      action='store',
                      dest='localip',
                      default="",
                      help='local ip')
    options, args = parser.parse_args()
    
    if options.filename:
        options.download = options.filename
    if not options.host or (not options.download and not options.upload):
        sys.stderr.write("Need filename and host\n")
        parser.print_help()
        sys.exit(1)

    #Keep track of download/upload progress based on DAT or ACK parckets received
    #Transferred bytes and ACK received
    class Progress(object):
        def __init__(self, out):
            self.progress = 0
            self.out = out

        def progresshook(self, pkt):
            if isinstance(pkt, tftpy.TftpPacketTypes.TftpPacketDAT):
                self.progress += len(pkt.data)
                self.out("Transferred %d bytes" % self.progress)
            elif isinstance(pkt, tftpy.TftpPacketTypes.TftpPacketOACK):
                self.out("Received OACK, options are: %s" % pkt.options)
        

    progresshook = Progress(log.info).progresshook

    tftp_options = {}
    if options.blksize:
        tftp_options['blksize'] = int(options.blksize)
    
    #Initialize tftp client 
    tclient = tftpy.TftpClient(options.host,
                               int(options.port),
                               tftp_options,
                               options.localip)
    
    #Checking for download or upload
    try:
        if options.download:
            if not options.output:
                options.output = os.path.basename(options.download)
            tclient.download(options.download,
                             options.output,
                             progresshook)
        elif options.upload:
            if not options.input:
                options.input = os.path.basename(options.upload)
            tclient.upload(options.upload,
                           options.input,
                           progresshook)
    except tftpy.TftpException as err:
        sys.stderr.write("%s\n" % str(err))
        sys.exit(1)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()