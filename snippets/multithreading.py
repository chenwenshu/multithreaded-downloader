from multiprocessing.dummy import Pool as ThreadPool


pool = ThreadPool(4)

# TODO: do something here with pool.map(func, list)

# close the pool and wait for the work to finish
pool.close()
pool.join()
