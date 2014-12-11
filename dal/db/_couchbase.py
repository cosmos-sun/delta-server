import time
from couchbase.connection import Connection
from couchbase.exceptions import *
import settings

from utils import log

cb = None


class GConnectionExtention(Connection):

    def load(self, key):
        """
        Call GConnection simple get and return its value.
        """
        val = self.get(key)
        return val and val.value

    def exist(self, key):
        """
        Check if an key exist in couchbase.
        Call simple get and check its value:
            None - key does not exist
            Otherwise - key exist
        """
        val = self.get(key).value
        return val is not None


def init_cb():
    global cb
    bucket = settings.COUCHBASE_BUCKET
    host = settings.COUCHBASE_HOST
    print bucket, host
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