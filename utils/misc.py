import base64

from dal.base import KeyValue
from utils import log, protocol_pb2
from utils.settings import ACTIVATE_PLAYER_NUMBER
from utils import protocol_pb2 as game_proto


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


def build_enum_type(name):
    return '_' + name.upper()

def assign_value(inst, data, proto=game_proto):
    for name, value in inst.DESCRIPTOR.fields_by_name.items():
        if not data or name not in data:
            continue
        attr = getattr(inst, name)
        if hasattr(attr, 'DESCRIPTOR'):
            assign_value(attr, data[name], proto)
        else:
            if type(data[name]) is list:
                l = []
                if hasattr(value.message_type, 'name') and getattr(value.message_type, 'name') is not None:
                    cls = getattr(proto, value.message_type.name)
                    for d in data[name]:
                        sub_inst = cls()
                        assign_value(sub_inst, d, proto)
                        l.append(sub_inst)
                else:
                    for d in data[name]:
                        l.append(d)
                getattr(inst, name).extend(l)
            else:
                if hasattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') and getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') is not None:
                        enum_type = getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type').name
                        enum_inst = getattr(proto, build_enum_type(enum_type))
                        d = enum_inst.values_by_name[data[name]].number
                        setattr(inst, name, d)
                else:
                    if data[name] is not None:
                        setattr(inst, name, data[name])