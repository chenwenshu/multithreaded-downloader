import click
import requests
import threading


def is_range_supported(get_request):
    try:
        return get_request.headers['Accept-Ranges'] != 'none'
    
    except KeyError:
        print('Multi-threaded Downloading not Supported!')
        return False


def range_download(url, start_byte, end_byte, filename):
    headers = {'Range': 'bytes={0}-{1}'.format(start_byte, end_byte)}
    
    r = requests.get(url = url, headers = headers, stream = True)
    
    with open(filename, 'r+b') as whole_file:  # opens the file without truncation
        whole_file.seek(start_byte)
        
        var = whole_file.tell()  # current position
        
        whole_file.write(r.content)


@click.command()
@click.option('-t', '--threads',
              default = 4,
              show_default = True,
              help = 'Number of Threads')
@click.option('-n', '--saved_name',
              help = 'Name of the Saved File')
@click.argument('url', type = click.Path())
def start_download(threads, saved_name, url):
    """A Multi-threaded Downloader Written in Python."""
    
    r = requests.get(url)
    
    if not is_range_supported(r):
        return
    
    if saved_name:
        filename = saved_name
    else:
        filename = url.split('/')[-1]
    
    try:
        file_size = int(r.headers['Content-Length'])
    except KeyError:
        print('Invalid URL')
        return
    
    segment_size = file_size // threads
    
    with open(filename, 'wb') as whole_file:
        whole_file.write(b'\0' * file_size)
        whole_file.close()
    
    for i in range(threads):
        start_byte = segment_size * i
        end_byte = start_byte + segment_size
        
        if i == threads - 1:
            end_byte = file_size
            
        thread = threading.Thread(target = range_download(),
                                  kwargs = {'url': url,
                                            'start_byte': start_byte,
                                            'end_byte': end_byte,
                                            'filename': filename})
        thread.setDaemon(True)
        thread.start()
        
    main_thread = threading.current_thread()
    for thread in threading.enumerate():
        if thread is main_thread:
            continue
        thread.join()
        
    print('{0} is downloaded.'.format(filename))


if __name__ == '__main__':
    start_download()
