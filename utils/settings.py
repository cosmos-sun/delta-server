import os
from utils.protocol_pb2 import OSType


VERSION = 00001

LISTEN_HOST = '0.0.0.0'	# listen on all, use docker to map to external IP
LISTEN_PORT = 8088

COUCHBASE_BUCKET = os.getenv("COUCHBASE_BUCKET", "default")
COUCHBASE_HOST = os.getenv("COUCHBASE_HOST",
    os.getenv("COUCHBASE_PORT_8091_TCP_ADDR", "10.21.2.63"))

ASSET_BUNDLE_ROOT = os.getenv("ASSET_BUNDLE_ROOT", "/opt/assetbundle")  # must be absolute path

USE_CACHE = False  # True

# TODO - set to half an hour?, 1 day for testing now.
SESSION_TTL_DELTA = 60 * 60 * 24

ACTIVATE_PLAYER_NUMBER = 50


# ============= Facebook settings ===============
# TODO - true for testing, turn off this if not implement facebook stuff
ENABLE_FACEBOOK = True

# Facebook mock up
FB_SAMPLE_ID = 0
# ============= Facebook settings ===============


# ============= IAB/IAP settings ================
# live
# INAPP_PURCHASE_VERIFY_URL = 'https://buy.itunes.apple.com/verifyReceipt'
INAPP_PURCHASE_VERIFY_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'
INAPP_PURCHASE_SANDBOX_VERIFY_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'

PURCHASE_ITEMS = {
    OSType.Value("IOS"): {
        "APPLE_PROD_1": {"price": 6,
                         "currency": "$",
                         "quantity": 50},
        "APPLE_PROD_2": {"price": 12,
                         "currency": "$",
                         "quantity": 100},
    },
    OSType.Value("Android"): {
        "Android_PROD_1": {"price": 6,
                           "currency": "$",
                           "quantity": 50},
        "Android_PROD_2": {"price": 12,
                           "currency": "$",
                           "quantity": 100},
    }
}
# ============= IAB/IAP settings end ================


# ============= Stats settings ======================
STATS_ZMQ_HOST = "127.0.0.1"
STATS_ZMQ_PORT = 5556
# ============= Stats settings end ==================
