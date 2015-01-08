# Fixtures for account.rst

from models.content import GameRule
from models.player import DeviceLink
from utils.protocol_pb2 import LoginAccount
from utils.protocol_pb2 import LoginAccountRep
from utils.protocol_pb2 import LoginAccountResultCode
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import SignType

def globs(globs):
    """Nose injects this as the global var dict"""
    globs.update(globals())
    return globs




called = []
player_ids = []

def setup_module(module):
    module.called[:] = []

def teardown_module(module):
    pass

def setup_test(test):
    called.append(test)
    test.var1 = 1
    pass
setup_test.__test__ = False

def teardown_test(test):
    # clear player info
    for p_id in player_ids:
        p = Player(id=p_id)
        p.delete()

        # device link
        for d in DeviceLink.load_by_attribute("player_id", p_id):
            d.delete()

        # creature team
        ct = CreatureTeam(player_id=p_id)
        ct.delete()

        # creatures
        for c in CreatureInstance.load_by_attribute("player_id", p_id):
            c.delete()
        delete_data(CreatureInstance.cid_key_tpl % p_id)
teardown_test.__test__ = False


import base64
import urllib
import urllib2
from unittest import TestCase
from dal import delete_data
from models.player import Player
from models.player import Session
from models.player import DeviceLink
from models.player import CreatureTeam
from models.player import CreatureInstance
from utils.misc import generate_message


def session_id_to_player_id(session_id):
    s = Session(id=session_id).load()
    return s.player_id

def post_message(msg, sub_url="player", session_id=None):
    base_url = "http://192.168.59.103:8088"
    sub_url = sub_url.strip("/")
    url_param = [base_url, sub_url]
    if "player" == sub_url:
        assert session_id is not None, "Missing session_id."
        url_param.append(session_id)
    url_param.append("")
    url = "/".join(url_param)
    name = type(msg).__name__
    data = {"name": name,
            "body": generate_message(msg)}
    payload = urllib.urlencode(data)
    req = urllib2.Request(url, payload)
    resp = urllib2.urlopen(req)
    return base64.b64decode(resp.read())