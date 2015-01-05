import time
from couchbase.connection import Connection
from couchbase.exceptions import *
from utils import settings
from utils import log


cb = None


class GConnectionExtention(Connection):
    
    def get_with_retry(self, key):
        """
        Like GConnect.get() but retries on temporary errors.
        """
        while True:
            try:
                val = self.get(key)
                return val
            except TemporaryFailError, e:
                log.warning("TemporaryFailError: can't get key '%s' - "
                            "retry in 2 secs...", key)
            time.sleep(2)
            continue

    def load(self, key):
        """
        Call GConnection simple get and return its value.
        """
        val = self.get_with_retry(key)
        return val and val.value

    def exist(self, key):
        """
        Check if an key exist in couchbase.
        Call simple get and check its value:
            None - key does not exist
            Otherwise - key exist
        """
        val = self.get_with_retry(key).value
        return val is not None


def init_cb():
    global cb
    bucket = settings.COUCHBASE_BUCKET
    host = settings.COUCHBASE_HOST
    log.debug("connecting to bucket '%s' on host '%s'", bucket, host)
    if bucket and host:
        while True:
            try:
                cb = GConnectionExtention(bucket=bucket, host=host, quiet=True)
                log.debug("connected")
                break
            except NetworkError, e:
                log.warning("NetworkError: can't connect to host '%s' - "
                            "retry in 5 secs...", host)
            except BucketNotFoundError, e:
                log.warning("BucketNotFoundError: can't find bucket '%s' "
                            "on host '%s' - retry in 5 secs...", bucket, host)
            time.sleep(5)
            continue

def get_cb():
    global cb
    if cb is None:
        init_cb()
    return cb
