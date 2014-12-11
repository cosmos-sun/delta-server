import uuid
import M2Crypto
import time
from datetime import datetime
from dal.base import *
from dal.db import db
from models.creature import CreatureInstance
from models.creature import CreatureTeam
from utils.exception import UnsupportedPlayerAction
from utils.protocol_pb2 import PlayerInfo


id_count = KeyValue('id_count')


class Player(Base):
    _oid_key = "id"

    id = LongAttr()
    name = TextAttr()
    level = IntAttr()
    agc_id = TextAttr()
    gc_id = TextAttr()
    facebook_id = LongAttr()
    sso_account_id = LongAttr()
    device_id = TextAttr()
    login_time = DateTimeAttr()
    xp = IntAttr()
    coins = IntAttr()
    _index_attributes = ["agc_id", "gc_id", "facebook_id", "sso_account_id",
                         "device_id"]

    achievements = ListAttr(TextAttr())

    def __init__(self, **kw):
        if not kw.get("id"):
            kw["id"] = id_count.incr(1, initial=1)
        if kw.get("is_new"):
            kw.setdefault("name", kw["id"])
            kw.setdefault("level", 1)
            kw.setdefault("login_time", datetime.now())
            kw.setdefault("xp", 0)
            kw.setdefault("coins", 100)

        super(Player, self).__init__(**kw)

        if kw.get('is_new'):
            self.init_detials()

    def init_detials(self):
        CreatureInstance(player_id=self.id).create('mouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('mouse_01',2,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('mouse_01',3,0,1,1,1,1)
        CreatureTeam.create(self.id, ([1,2,3], [3,2,1], None, None, None)).store()

    def set_info(self, rep, simple_mode=False):
        pid = int(self.id)
        rep.userId = pid
        rep.name = str(self.name)
        rep.xp = self.xp

        if not simple_mode:
            creatures = CreatureInstance.get_all_by_player(self.id)
            rep.creaturebox.extend(creatures)

            CreatureTeam.get_proto_class(self.id, rep.teams)
        return rep

    def to_proto_class(self, simple_mode=False):
        player_info = PlayerInfo()
        return self.set_info(player_info, simple_mode)

    def delete(self):
        raise UnsupportedPlayerAction("Can't delete player instance.")

    def get_help_creature(self):
        """
        Player's 1st team's 1st creature will be the default help creature.
        If all team is empty, use the first creature of this player.
        """
        teams = CreatureTeam(player_id=self.id)
        active_team = teams.get_active_team()
        if active_team:
            data = {"c_id": active_team[0],
                    "player_id": self.id}
            creature = CreatureInstance(**data).load()
        else:
            creatures = CreatureInstance.load_by_attribute("player_id",
                                                           self.id)
            creature = creatures and creatures[0]
        return creature

    def get_active_creatures(self):
        teams = CreatureTeam(player_id=self.id)
        teams = teams.get_teams()
        active_creatures = set()
        for t in teams:
            active_creatures.update(t)
        return active_creatures


class Session(Base):
    _oid_key = "id"
    _index_attributes = ["player_id"]

    id = TextAttr()
    player_id = LongAttr()

    def __init__(self, **kw):
        if "id" not in kw:
            kw["id"] = self.generate_session()
        super(Session, self).__init__(**kw)

    def generate_session(self):
        return str(uuid.UUID(bytes=M2Crypto.m2.rand_bytes(16)))

    def refresh_session(self):
        # TODO - move ttl_delta to config
        ttl_delta = 60 * 60 * 24  # 1 day for testing
        ttl = int(time.time()) + ttl_delta
        db.touch(Session(id=self.id)._get_key(), ttl)
        db.touch(Session._get_index_key("player_id", self.player_id), ttl)
        return

