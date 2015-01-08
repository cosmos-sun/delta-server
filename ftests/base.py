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
from utils.misc import latest_login_players
from utils.protocol_pb2 import LoginAccount
from utils.protocol_pb2 import LoginAccountRep
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import SignType


class BaseFtest(TestCase):
    player_ids = set()
    # player account info
    device_id = "test_account"
    name = "happylatte"

    def setUp(self):
        pass

    def tearDown(self):
        # clear player info
        for p_id in self.player_ids:
            p = Player(id=p_id).load()
            p.delete()

            # device link
            for d in DeviceLink.load_by_attribute("player_id", p_id):
                d.delete()

            # creature team
            ct = CreatureTeam(player_id=p_id).load()
            ct.delete()

            # creatures
            for c in CreatureInstance.load_by_attribute("player_id", p_id):
                c.delete()
            delete_data(CreatureInstance.cid_key_tpl % p_id)

            # session
            for s in Session.load_by_attribute("player_id", p_id):
                s.delete()

            # remove from latest login list
            active_players = latest_login_players.load()
            if p_id in active_players:
                active_players.remove(p_id)
                latest_login_players.store(active_players)

    def session_id_to_player_id(self, session_id):
        s = Session(id=session_id).load()
        return s.player_id

    def create_player(self, device_id=device_id, name=name,
                      sign_type=SignType.Value("DEVICE"), pip_id=None,
                      os_type=OSType.Value("IOS"),
                      pre_device_id=None):
        """
        LoginAccount to create a player and return the session id
        and LoginAccountRep
        """
        acc = LoginAccount()
        acc.device_id = device_id
        acc.name = name
        acc.type = sign_type
        acc.info.os_type = os_type
        if pip_id:
            acc.pip_id = pip_id
        if pre_device_id:
            acc.pre_device_id = pre_device_id
        msg = self.post_message(acc, LoginAccountRep, "account")
        self.player_ids.add(msg.player_info.userId)
        return msg.session_id, msg

    def post_message(self, msg, resp_msg, sub_url="player", session_id=None):
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
        return resp_msg.FromString(base64.b64decode(resp.read()))
