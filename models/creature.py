from dal.base import *
from utils.exception import CreatureDisabledAction
from utils import protocol_pb2 as proto
from models.content import creature_types


class CreatureInstance(Base):
    _oid_key = "c_id"
    _index_attributes = ["player_id"]
    _parent_key = "player_id"
    _loaded = False
    _type = None

    player_id = IntAttr()
    c_id = IntAttr()

    slug = TextAttr()
    id = IntAttr()
    xp = IntAttr()
    level = IntAttr()
    plusHP = IntAttr()
    plusAttack = IntAttr()
    plusSpeed = IntAttr()
    plusLuck = IntAttr()

    def get_id(self, pid):
        id_count = KeyValue('creature_id:%s' % pid)
        return id_count.incr(1, initial=1)

    def _save(self, slug, level=1, xp=0, plus_hp=0, plus_attack=0,
              plus_speed=0, plus_luck=0):
        slug = slug.lower()
        creature_type = creature_types.get(slug)
        self.slug = slug
        self.id = creature_type.displayID
        self.xp = xp
        self.level = level
        self.plusHP = plus_hp
        self.plusAttack = plus_attack
        self.plusSpeed = plus_speed
        self.plusLuck = plus_luck
        self.store()

    def create(self, slug, level=1, xp=0,
               plusHP=0, plusAttack=0, plusSpeed=0, plusLuck=0):
        self.c_id = self.get_id(self.player_id)
        self._save(slug, level, xp, plusHP, plusAttack, plusSpeed, plusLuck)
        return self

    def _upgrade(self, new_slug):
        self._save(new_slug, plus_hp=self.plusHP, plus_attack=self.plusAttack,
                   plus_speed=self.plusSpeed, plus_luck=self.plusLuck)

    @classmethod
    def get_all_by_player(cls, pid):
        rep = []
        for c in CreatureInstance.load_by_attribute('player_id', pid):
            rep.append(c.to_proto_class())
        return rep

    def to_proto_class(self):
        c = proto.CreatureInstance()
        c.cid = self.c_id
        c.slug = self.slug
        c.id = self.id
        c.xp = self.xp
        c.level = self.level
        c.plusHP = self.plusHP
        c.plusAttack = self.plusAttack
        c.plusSpeed = self.plusSpeed
        c.plusLuck = self.plusLuck
        return c

    def _do_load(self):
        if not self._loaded:
            self.load()
            self._loaded = True
            self._type = creature_types.get(self.slug)

    def sale_price(self):
        self._do_load()
        # TODO - Design
        return self.level * 500

    def fuse_currency(self):
        # TODO - Design
        return 300

    def evolve_currency(self):
        # TODO - Design
        return 300

    def ascend_currency(self):
        # TODO - Design
        return 300

    def is_max_level(self):
        self._do_load()
        return self.level == self._type.maxLevel

    def fuse_trans_xp(self):
        """
        Transform creature to xp to fuse others.
        """
        self._do_load()
        # TODO - Design
        return self.level * 500

    def level_up(self, xp):
        self._do_load()
        self.xp += xp
        # TODO - Design: get level up XP
        next_level = self.level + 1
        while self.xp > next_level * 100 and next_level <= self._type.maxLevel:
            self.level = next_level
            self.xp -= next_level * 100
            next_level += 1
        self.store()

    def support_evolve(self):
        self._do_load()
        return bool(self._type.evolutionSlug)

    def evolution_materials(self):
        self._do_load()
        # TODO - Design
        return {"coins": 5}

    def evolve(self):
        self._do_load()
        evolution_slug = self._type.evolutionSlug
        if not evolution_slug:
            raise CreatureDisabledAction(slug=self.slug, action="evolution")
        self._upgrade(evolution_slug)

    def get_transcend(self):
        self._do_load()
        return self._type.transcend

    def transcend(self):
        transcend = self.get_transcend()
        transcend_slug = transcend and transcend.transcendSlug
        if not transcend_slug:
            raise CreatureDisabledAction(slug=self.slug, action="transcend")
        self._upgrade(transcend_slug)


class CreatureTeam(Base):
    _oid_key = "player_id"

    player_id = IntAttr()
    team1 = ListAttr(IntAttr())
    team2 = ListAttr(IntAttr())
    team3 = ListAttr(IntAttr())
    team4 = ListAttr(IntAttr())
    team5 = ListAttr(IntAttr())

    @classmethod
    def create(cls, pid, teams):
        data =  {'player_id': pid,
                 'team1': teams[0],
                 'team2': teams[1],
                 'team3': teams[2],
                 'team4': teams[3],
                 'team5': teams[4],
        }
        return CreatureTeam(**data)

    @classmethod
    def store_from_proto(cls, pid, protos):
        t = cls(player_id=pid).load()
        t.team1 = [i for i in protos[0].creaturesIds]
        t.team2 = [i for i in protos[1].creaturesIds]
        t.team3 = [i for i in protos[2].creaturesIds]
        t.team4 = [i for i in protos[3].creaturesIds]
        t.team5 = [i for i in protos[4].creaturesIds]

        t.store()

    @classmethod
    def get_proto_class(cls, pid, proto):
        def _assign_ids(ct, pt):
            if not ct:
                return
            t = pt.add()
            for i in ct:
                t.creaturesIds.append(i)
        ts = cls(player_id=pid).load()
        _assign_ids(ts.team1, proto)
        _assign_ids(ts.team2, proto)
        _assign_ids(ts.team3, proto)
        _assign_ids(ts.team4, proto)
        _assign_ids(ts.team5, proto)

    def get_active_team(self):
        self.load()
        for index in range(1, 6):
            active_team = getattr(self, "team%s" % index)
            if active_team:
                return active_team
        return []

    def get_teams(self):
        self.load()
        teams = []
        for index in range(1, 6):
            team = getattr(self, "team%s" % index)
            if team:
                teams.append(team)
        return teams


class MaterialInfo(Base):
    _oid_key = "material_id"

    material_id = IntAttr()

class BoostInfo(Base):
    _oid_key = "boost_id"
    boost_id = IntAttr()
    attack = IntAttr()
    speed = IntAttr()
    hp = IntAttr()
    cd = IntAttr()
    aiming = IntAttr()

class EvolveInfo(Base):
    _oid_key = "slug"

    slug = TextAttr()
    elapsed = IntAttr()
    endtime = IntAttr()

class MissionInst(Base):
    _oid_key = "misstion_id"

    misstion_id = IntAttr()
    progress = IntAttr()