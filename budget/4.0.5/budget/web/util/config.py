import os 

class Config(object):

    INACTIVE_DAYS = 365
    USER = None 

    def __init__(self, *args, **kwargs):

        for k in os.environ:
            if k in dir(Config):
                self.__setattr__(k, os.environ[k])