import uuid
import M2Crypto
from datetime import datetime
from time import time
from dal.base import *
from dal.db import db
from models.creature import CreatureInstance
from models.creature import CreatureTeam
from utils.exception import NotEnoughEnergy
from utils.exception import UnsupportedPlayerAction
from utils.protocol_pb2 import PlayerInfo
from models.content import GameRule

id_count = KeyValue('id_count')
ENERGY_COUNTDOWN = 30  # TODO - Design


class Player(Base):
    _oid_key = "id"

    id = LongAttr()
    name = TextAttr()
    level = IntAttr()
    agc_id = TextAttr()
    gc_id = TextAttr()
    facebook_id = LongAttr()
    device_id = TextAttr()  # Record the device create the player
    login_time = DateTimeAttr()
    xp = IntAttr()
    coins = IntAttr()
    hearts = IntAttr()
    gems = IntAttr()
    energy = IntAttr()
    energy_update_time = IntAttr()
    progress = IntAttr()
    stone_s = IntAttr()
    stone_m = IntAttr()
    stone_l = IntAttr()
    stone_x = IntAttr()
    stone_fire_s = IntAttr()
    stone_fire_l = IntAttr()
    stone_wood_s = IntAttr()
    stone_wood_l = IntAttr()
    stone_water_s = IntAttr()
    stone_water_l = IntAttr()
    stone_light_s = IntAttr()
    stone_light_l = IntAttr()
    stone_dark_s = IntAttr()
    stone_dark_l = IntAttr()

    _index_attributes = ["agc_id", "gc_id", "facebook_id", "device_id"]

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
            kw.setdefault("gems", 10)
            kw.setdefault("energy", 20)
            kw.setdefault("hearts", 0)
            kw.setdefault("progress", 0)
            kw.setdefault("stone_s", 0)
            kw.setdefault("stone_m", 0)
            kw.setdefault("stone_l", 0)
            kw.setdefault("stone_x", 0)
            kw.setdefault("stone_fire_s", 0)
            kw.setdefault("stone_fire_l", 0)
            kw.setdefault("stone_wood_s", 0)
            kw.setdefault("stone_wood_l", 0)
            kw.setdefault("stone_water_s", 0)
            kw.setdefault("stone_water_l", 0)
            kw.setdefault("stone_light_s", 0)
            kw.setdefault("stone_light_l", 0)
            kw.setdefault("stone_dark_s", 0)
            kw.setdefault("stone_dark_l", 0)

        super(Player, self).__init__(**kw)

        if kw.get('is_new'):
            self.init_detials()

    def init_detials(self):
        CreatureInstance(player_id=self.id).create('firemouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('woodmouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('watermouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('lightmouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('darkmouse_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('firemonkey_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('woodmonkey_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('watermonkey_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('lightmonkey_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('darkmonkey_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('fireaynt_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('woodaynt_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('wateraynt_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('lightaynt_01',1,0,1,1,1,1)
        CreatureInstance(player_id=self.id).create('darkaynt_01',1,0,1,1,1,1)
        CreatureTeam.create(self.id, ([1,2,3], [3,2,1], None, None, None)).store()

    def add_xp(self, xp):
        self.xp += xp
        while self.xp >= self._get_level_config(self.level + 1).get("xp"):
            self.xp -= self._get_level_config(self.level + 1).get("xp")
            self.level += 1

    def set_info(self, rep, simple_mode=False):
        pid = int(self.id)
        rep.userId = pid
        rep.name = str(self.name)
        rep.xp = self.xp

        if not simple_mode:
            rep.coins = self.coins or 0
            rep.gems = self.gems or 0
            rep.hearts = self.hearts or 0
            rep.energy = self.get_energy()

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

    def _get_level_config(self, level=None):
        level = level or self.level
        DEFAULT_CONFIG = {"maxEnergy": 1200,
                          "maxFriend": 2100,
                          "xp": 1000000}
        level_config = GameRule.player_level.get(level, DEFAULT_CONFIG)
        return level_config

    def get_max_energy(self):
        level_config = self._get_level_config()
        return level_config.get("maxEnergy")

    def _energy_update_time(self):
        return self.energy_update_time or 0

    def _update_energy(self, val, do_store=False):
        energy = self.get_energy()
        if energy + val < 0:
            return False
            #raise NotEnoughEnergy(self.id, energy, -val)
        self.energy = energy + val
        self.energy_update_time = int(time())
        if do_store:
            self.store()
        return True

    def get_energy(self):
        energy = self.energy or 0
        max_energy = self.get_max_energy()
        now = int(time())
        update_time = self._energy_update_time()
        return min(energy + (now - update_time) / ENERGY_COUNTDOWN, max_energy)

    def get_energy_countdown(self):
        """
        Return the countdown time to refill energy.
        """
        energy = self.get_energy()
        max_energy = self.get_max_energy()
        if energy >= max_energy:
            return 0
        since_last_update = int(time()) - self._energy_update_time()
        _countdown = (max_energy - energy) * ENERGY_COUNTDOWN
        if since_last_update >= _countdown:
            return 0
        return _countdown - since_last_update

    def add_energy(self):
        # add max energy each time.
        return self._update_energy(self.get_max_energy())

    def spend_energy(self, val, do_store=False):
        return self._update_energy(-val, do_store=do_store)

    def set_progress(self, p):
        p = self.progress if p < self.progress else p
        self.progress = p


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
        ttl = int(time()) + ttl_delta
        db.touch(Session(id=self.id)._get_key(), ttl)
        db.touch(Session._get_index_key("player_id", self.player_id), ttl)
        return


class DeviceLink(Base):
    _oid_key = "device_id"
    _index_attributes = ["player_id"]

    device_id = TextAttr()
    player_id = LongAttr()
