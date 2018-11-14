import sys, logging
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
    parser.add_option('-i',
                      '--ip',
                      type='string',
                      help='ip to bind',
                      default="")
    parser.add_option('-p',
                      '--port',
                      type='int',
                      help='specify port (default: 69)',
                      default=69)
    parser.add_option('-r',
                      '--root',
                      type='string',
                      help='specify directory',
                      default=None)
    
    options, args = parser.parse_args()

    if not options.root:
        parser.print_help()
        sys.exit(1)

    #Initialize tftp server 
    server = tftpy.TftpServer(options.root)
    try:
        server.listen(options.ip, options.port)
    except tftpy.TftpException as err:
        sys.stderr.write("%s\n" % str(err))
        sys.exit(1)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
