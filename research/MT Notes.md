# Multi-threadedDownloading with Python
## Libraries
### Multi-threading

#### `multiprocessing` _vs_ `multiprocessing.dummy`  

`multiprocessing` | `multiprocessing.dummy`  
--- | ---  
processes | threads
CPU-intensive tasks | IO
module | wrapper around `threading` module

### Downloading

#### `requests` module

To download a large file without hogging memory, set the `stream` parameter to `True` for `requests.get()` call.
* Download is delayed
* Headers are downloaded
* Connection is kept open

To download the content chunk by chunk, set the `chunk_size` parameter for `requests.iter_contect()` call.
* A generator is used to request content

## HTTP Requests

### Partial Downloadability Check

The `Accept-Ranges` response HTTP header is a marker used by the server to advertise its support of partial requests.  

The value of this field indicates the unit that can be used to define a range. A `none` value or omitting the header indicate that the server do not support for partial requests.

### Request a Specific Range

#### `Range` header

Status Code | Indication
:---: | :---:
206 | Partial Content
416 | Range Not Satisfiable
200 | `Range` header ignored

##### Syntax for Single Part Retrieval
`Range: <unit>=<range-start>-`  
`Range: <unit>=<range-start>-<range-end>`

##### HTTP Response
`Content-Length` header now indicates the size of the requested range, instead of the full size of the file.

## References
[Parallelism in one line](http://chriskiehl.com/article/parallelism-in-one-line/)  
[Intro to Threads and Processes in Python](https://medium.com/@bfortuner/python-multithreading-vs-multiprocessing-73072ce5600b)  
[Using the `requests` module to download large files efficiently](http://masnun.com/2016/09/18/python-using-the-requests-module-to-download-large-files-efficiently.html)  
[HTTP range requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)  
[Simple Multithreaded Download Manager in Python](https://www.geeksforgeeks.org/simple-multithreaded-download-manager-in-python/)