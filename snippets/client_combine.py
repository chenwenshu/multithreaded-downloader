import os

from glob import glob
from shutil import copyfileobj


def combine(filename):
    name, ext = os.path.splitext(filename)
    file_list = sorted(glob(name + '*' + ext))
    print(file_list)
    
    with open(filename, 'a+b') as whole_file:
        for partial in file_list:
            partial_file = open(partial, 'r+b')
            copyfileobj(partial_file, whole_file)
            partial_file.close()
            
        whole_file.close()
    
    print('Succesfully combined file {}'.format(filename))
    return


if __name__ == '__main__':
    combine('/Users/wenshu/PycharmProjects/MultithreaDownloader/snippets/temp/Strawman Proposal.pdf')