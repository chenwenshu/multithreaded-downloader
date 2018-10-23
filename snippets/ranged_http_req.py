import requests

# TODO: check server Accept-Range
range_accepted = True

# if not range_accepted: done

start_byte = 0
end_byte = 1
url = 'https://www.google.com'
filename = 'filename'

header = {'Range': 'bytes={0}-{1}'.format(start_byte, end_byte)}

r = requests.get(url, headers = header, stream = True)

with open(filename, 'r+b') as f:
    f.seek(start_byte)
    f.write(r.content)
