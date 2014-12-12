import base64

from utils import log, protocol_pb2


active_player_num = 50
latest_login_players = []


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
    global latest_login_players
    if player_id in latest_login_players:
        latest_login_players.remove(player_id)
    latest_login_players.append(player_id)
    latest_login_players = latest_login_players[-active_player_num:]
    return latest_login_players


def get_latest_login_players():
    return latest_login_players
