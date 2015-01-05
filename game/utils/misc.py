import base64

from dal.base import KeyValue
from utils import log, protocol_pb2
from utils.settings import ACTIVATE_PLAYER_NUMBER


latest_login_players = KeyValue("LATEST_LOGIN_PLAYERS")


def parse_message(name, body):
    #cls = globals()[name]
    cls = getattr(protocol_pb2, name)
    event = None
    try:
        event = cls()
        msg=body
        Base64=base64.b64decode(msg)
        event.ParseFromString(Base64)
    except Exception, e:
        log.error('Error parse_message: %s', e)

    return event


def generate_message(e):
    _msg=e.SerializeToString()

    #cnt=e.ByteSize()
    #msg=base64.b64encode(_msg[:cnt])

    msg = base64.b64encode(_msg)
    #print type(e), len(msg)
    return msg


def update_latest_login_players(player_id):
    activate_players = get_latest_login_players()
    if player_id in activate_players:
        activate_players.remove(player_id)
    activate_players.append(player_id)
    activate_players = activate_players[-ACTIVATE_PLAYER_NUMBER:]
    latest_login_players.store(activate_players)
    return activate_players


def get_latest_login_players():
    return latest_login_players.load() or []
