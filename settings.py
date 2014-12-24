import os

VERSION = 00001

LISTEN_HOST = '0.0.0.0'	# listen on all, use docker to map to external IP
LISTEN_PORT = 8088

COUCHBASE_BUCKET = os.getenv("COUCHBASE_BUCKET", "default")
COUCHBASE_HOST = os.getenv("COUCHBASE_HOST",
    os.getenv("COUCHBASE_PORT_8091_TCP_ADDR", "10.21.2.97"))

ASSET_BUNDLE_ROOT = os.getenv("ASSET_BUNDLE_ROOT", "/opt/assetbundle")  # must be absolute path

USE_CACHE = False # True
