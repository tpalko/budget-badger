import json 
import redis 
from django.core import serializers
import logging 

rds = redis.Redis(host='127.0.0.1', port=6379)
logger = logging.getLogger(__name__)

def cache_store(key, val):
    rds.set(key, json.dumps(val))

def cache_fetch(key, callback=None):
    logger.warning(f'[{key}] fetching objects')
    obj = rds.get(key)
    if obj:
        logger.warning(f'[{key}] cache HIT!')
        obj = json.loads(obj)
    else:
        logger.warning(f'[{key}] cache MISS')
        if callback:
            obj = callback()
            cache_store(key, obj)
    return obj 

def _serialize(objects):
    return serializers.serialize("json", objects)

def _deserialize(objects):    
    return [ r.object for r in serializers.deserialize("json", objects) ]

def _cache_store_objects(key, objects):
    logger.warning(f'[{key}] serializing {len(objects)} objects')
    serialized_objects = _serialize(objects)
    logger.warning(f'[{key}] {len(objects)} objects serialized')
    rds.set(key, serialized_objects)
    return serialized_objects

def cache_fetch_objects(key, callback=None):
    logger.warning(f'[{key}] fetching objects')
    records = rds.get(key)
    if not records:
        logger.warning(f'[{key}] cache MISS')
        if callback:
            records = _cache_store_objects(key, callback())
            logger.warning(f'[{key}] {len(records)} objects stored')
        else:
            logger.warning(f'[{key}] no callback provided, returning nothing')
    else:
        logger.warning(f'[{key}] cache HIT!')
    
    if records:
        logger.warning(f'[{key}] deserializing data size {len(records)}')
        records = _deserialize(records)
        logger.warning(f'[{key}] deserialized {len(records)} records')

    return records 