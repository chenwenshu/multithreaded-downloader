import os
from math import ceil

from fsplit.filesplit import FileSplit


def segment(num_threads, filename):
    if not os.path.exists('./temp'):
        os.mkdir('./temp')
    
    file_size = int(os.stat(filename).st_size)
    chunk_size = ceil(file_size / num_threads)
    
    fs = FileSplit(filename, chunk_size, './temp')
    fs.split()

    name, ext = os.path.splitext(filename)
    second_last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, num_threads, ext))
    last_filename = os.path.join('./temp', "{0}_{1}{2}".format(name, num_threads + 1, ext))

    # To get rid of the trailing file
    with open(second_last_filename, 'a+b') as f:
        last_file = open(last_filename, 'r+b')
        tail = last_file.read()
        last_file.close()

        f.write(tail)
        f.close()

    os.remove(last_filename)
    
    return


if __name__ == '__main__':
    segment(4, 'Strawman Proposal.pdf')
