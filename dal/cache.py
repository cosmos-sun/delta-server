from dogpile.cache import make_region
from dogpile.cache.api import NO_VALUE

CACHE_SECONDS = 30

region = make_region().configure(
        'dogpile.cache.memory',
        expiration_time=CACHE_SECONDS)

def load(key):
    val = region.get(key)
    if val == NO_VALUE:
        return None
    else:
        return val

def store(key, data):
    region.set(key, data)

def delete(key):
    region.delete(key)