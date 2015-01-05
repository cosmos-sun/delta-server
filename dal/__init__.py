import _cache
import db
from utils.settings import USE_CACHE


def load_data(key):
    data = None
    if USE_CACHE:
        data = _cache.load(key)
    if not data:
        data = db.db.load(key)
    return data


def store_data(key, val):
    if USE_CACHE:
        _cache.store(key, val)
    db.db.set(key, val)


def delete_data(key):
    if USE_CACHE:
        _cache.delete(key)
    db.db.delete(key)