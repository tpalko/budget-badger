import logging 

logger = logging.getLogger(__name__)

class Cache(object):

    __instance = None 
    _store = None 

    @staticmethod 
    def kwargs_to_key(**kwargs):
        return ":".join([ f'{k}={kwargs[k]}' for k in kwargs ])
    
    @staticmethod 
    def invalidate_by_kwargs(**kwargs):
        Cache.getInstance().invalidate(Cache.kwargs_to_key(**kwargs))
    
    @staticmethod 
    def invalidate(key=None):

        if key is None:
            Cache.getInstance().__instance._store = {} 
            # for k in Cache.getInstance().__instance._store.keys():
            #     del Cache.getInstance().__instance._store[k]
        elif key != "":
            if key in Cache.getInstance().__instance._store:
                del Cache.getInstance().__instance._store[key] 

    @staticmethod 
    def store_by_kwargs(value, **kwargs):
        return Cache.getInstance().store(":".join([ f'{k}={kwargs[k]}' for k in kwargs ]), value)

    @staticmethod
    def store(key, value):
        Cache.getInstance().__instance._store[key] = value 
        return key 
    
    @staticmethod 
    def fetch_by_kwargs(**kwargs):
        key = ":".join([ f'{k}={kwargs[k]}' for k in kwargs ])
        return Cache.getInstance().fetch(key)
        
    @staticmethod
    def fetch(key):
        value = None 
        if key in Cache.__instance._store:
            value = Cache.getInstance().__instance._store[key]
        else:
            logger.debug(f'no cache entry for {key}')
        return value, key 
    
    @staticmethod
    def getInstance():
        if not Cache.__instance:
            Cache()
        return Cache.__instance

    def __init__(self, *args, **kwargs):
        if Cache.__instance:
            raise Exception("Cache instance exists!")
        self._store = {} 
        Cache.__instance = self 