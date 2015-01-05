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
from utils.protocol_pb2 import MaterialData
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import PlayerInfo
from utils.settings import SESSION_TTL_DELTA
from models.content import GameRule

id_count = KeyValue('id_count')


class Player(Base):
    _oid_key = "id"

    # static attr
    id = LongAttr()
    name = TextAttr()
    agc_id = TextAttr()
    gc_id = TextAttr()
    facebook_id = LongAttr()
    device_id = TextAttr()  # Record the device create the player
    os_type = IntAttr()

    # game process
    login_time = DateTimeAttr()
    xp = IntAttr()
    level = IntAttr()
    energy = IntAttr()
    energy_update_time = IntAttr()
    progress = IntAttr()
    max_creatures = IntAttr()

    # monetary
    coins = IntAttr()
    hearts = IntAttr()
    gems = IntAttr()

    # materials
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
            kw.setdefault("login_time", datetime.now())
            for key, val in GameRule.default_player_settings.get("attr").iteritems():
                kw.setdefault(key, val)
            for material in GameRule.material_slugs:
                kw.setdefault(material, 0)

        super(Player, self).__init__(**kw)

        if kw.get('is_new'):
            self.init_detials(kw.get("default_creatures"))

    def init_detials(self, default_creatures):
        c_ids = []
        if default_creatures:
            for slug, attr in default_creatures.iteritems():
                c = CreatureInstance(player_id=self.id).create(slug, **attr)
                c_ids.append(c.oid)
        else:
            for c_slug in GameRule.default_player_settings.get("creatures"):
                c = CreatureInstance(player_id=self.id).create(c_slug)
                c_ids.append(c.oid)

        c_len = len(c_ids)
        if c_len < CreatureTeam.team_length:
            team = c_ids + [0] * (CreatureTeam.team_length - c_len)
        else:
            team = c_ids[:CreatureTeam.team_length]
        CreatureTeam.create(self.id, team1=team).store()

    def add_xp(self, xp):
        def _level_up_xp():
            return self._get_level_config(self.level + 1).get("xp")

        self.xp += xp
        leve_up_xp = _level_up_xp()
        while self.xp >= leve_up_xp:
            self.xp -= leve_up_xp
            self.level += 1
            leve_up_xp = _level_up_xp()

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
            rep.maxCreatures = self.max_creatures or 40
            for slug in GameRule.material_slugs:
                count = getattr(self, slug)
                if count:
                    m = MaterialData()
                    m.slug = slug
                    m.count = count
                    rep.materialbox.add(slug=slug, count=count)

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
        energy, countdown = self.get_energy(with_countdown=True)
        if energy + val < 0:
            return False
            #raise NotEnoughEnergy(self.id, energy, -val)
        self.energy = energy + val

        update_time = int(time())
        if self.energy < self.get_max_energy():
            # deduction the countdown if not met max energy
            update_time -= countdown
        self.energy_update_time = update_time
        if do_store:
            self.store()
        return True

    def get_energy(self, with_countdown=False):
        energy, countdown = self._get_energy()
        if with_countdown:
            return energy, countdown
        return energy

    def _get_energy(self):
        energy = self.energy or 0
        max_energy = self.get_max_energy()
        if energy >= max_energy:
            return energy, 0

        # calculate countdown if not meet max energy
        since_last_update = int(time()) - self._energy_update_time()
        energy_delta = since_last_update / GameRule.energy_countdown
        energy += energy_delta
        if energy >= max_energy:
            return max_energy, 0
        countdown = since_last_update % GameRule.energy_countdown
        return energy, countdown

    def get_energy_countdown(self):
        """
        Return the countdown time to refill energy.
        """
        energy = self.get_energy()
        max_energy = self.get_max_energy()
        if energy >= max_energy:
            return 0
        since_last_update = int(time()) - self._energy_update_time()
        _countdown = (max_energy - energy) * GameRule.energy_countdown
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

    def modify_material(self, slug, val):
        setattr(self, slug, getattr(self, slug) + val)

    def buy_creature_space(self):
        self.max_creatures += GameRule.extend_creature_space

    def get_os_type(self):
        return self.os_type or OSType.Value("IOS")


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
        ttl = int(time()) + SESSION_TTL_DELTA
        db.touch(Session(id=self.id)._get_key(), ttl)
        db.touch(Session._get_index_key("player_id", self.player_id), ttl)
        return


class DeviceLink(Base):
    _oid_key = "device_id"
    _index_attributes = ["player_id"]

    device_id = TextAttr()
    player_id = LongAttr()

class PassedDungeons(Base):
    _oid_key = "player_id"

    player_id = LongAttr()
    slugs = ListAttr(TextAttr())
