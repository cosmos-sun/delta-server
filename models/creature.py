import math
import random
from dal.base import *
from utils.exception import CreatureDisabledAction
from utils.protocol_pb2 import CreatureInstance as CreatureProto
from models.content import GameRule


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
        creature_type = GameRule.creature_types.get(slug)
        self.slug = slug
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

    def info(self):
        return self._data

    @classmethod
    def get_all_by_player(cls, pid):
        rep = []
        for c in CreatureInstance.load_by_attribute('player_id', pid):
            rep.append(c.to_proto_class())
        return rep

    def to_proto_class(self):
        c = CreatureProto()
        c.cid = self.c_id
        c.slug = self.slug
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
            self._type = GameRule.creature_types.get(self.slug)

    @property
    def element(self):
        self._do_load()
        return self._type.element

    def sale_price(self):
        self._do_load()
        star = self._type.starRating
        params = GameRule.configs.get("sellingParams")
        param_a = params.get("paramA", 2.42)
        param_b = params.get("paramB", 100)
        param_c = params.get("paramC", 100)
        price = round(math.pow(star, param_a)) * param_b + self.level * param_c
        return int(price)

    def fuse_currency(self):
        self._do_load()
        star = self._type.starRating
        params = GameRule.configs.get("fusingParams")
        param_a = params.get("softCurrencyCostParamA", 1500)
        param_b = params.get("softCurrencyCostParamB", 1)
        param_c = params.get("softCurrencyCostParamC", 100)
        return int(star * param_a + (self.level - param_b) * param_c)

    def _get_evolve_config(self):
        self._do_load()
        star = self._type.starRating
        evolve_config = GameRule.evolve_config.get(star)
        return evolve_config

    def evolve_currency(self):
        evolve_config = self._get_evolve_config()
        return evolve_config.get("softCurrency")

    def ascend_currency(self):
        # TODO - Design
        return 300

    def is_max_level(self):
        self._do_load()
        return self.level == self._type.maxLevel

    def is_same_element(self, other):
        if isinstance(other, str):
            # handle slug
            c_type = GameRule.creature_types.get(other)
            return self.element == c_type.element
        else:
            # handle CreatureInstance
            return self.element == other.element

    def is_same_series(self, other):
        slug = isinstance(other, str) and other or other.slug
        series = GameRule.creature_series.get(self.slug)
        return slug in series

    def fuse_mega_odds(self, same_ele_num, feeders_num):
        self._do_load()
        params = GameRule.configs.get("fusingParams")
        param_a = params.get("megaFusionChanceParamA")
        param_b = params.get("megaFusionChanceParamB")
        odds_mego = param_a * same_ele_num / feeders_num + param_b
        if random.random() <= odds_mego:
            return True
        return False

    def fuse_trans_xp(self, eater):
        """
        Transform creature to xp to fuse others.
        """
        self._do_load()
        star = self._type.starRating
        params = GameRule.configs.get("fusingParams")
        param_a = params.get("xpGainParamA", 300)
        param_b = params.get("xpGainParamB", 120)
        param_c = params.get("xpGainParamC", 1)
        if self.is_same_element(eater):
            param_c += params.get("xpGainParamD", 0.25)
        return int((star * param_a + star * self.level * param_b) * param_c)

    def fuse_plus_hp(self, eater):
        self._do_load()
        if self.plusHP:
            params = GameRule.configs.get("fusingParams")
            param_a = params.get("plusHPInheritParamA", 0.25)
            param_b = params.get("plusHPInheritParamB", 2)
            if self.is_same_element(eater):
                param_b += 1
            return param_a * param_b * self.plusHP
        return 0

    def fuse_plus_attack(self, eater):
        self._do_load()
        if self.plusAttack:
            params = GameRule.configs.get("fusingParams")
            param_a = params.get("plusAtkInheritParamA", 0.25)
            param_b = params.get("plusAtkInheritParamB", 2)
            if self.is_same_element(eater):
                param_b += 1
            return param_a * param_b * self.plusAttack
        return 0

    def fuse_plus_speed(self, eater):
        self._do_load()
        if self.plusSpeed:
            params = GameRule.configs.get("fusingParams")
            param_a = params.get("plusSpdInheritParamA", 0.25)
            param_b = params.get("plusSpdInheritParamB", 2)
            if self.is_same_element(eater):
                param_b += 1
            return param_a * param_b * self.plusSpeed
        return 0

    def fuse_plus_luck(self, eater):
        self._do_load()
        if self.plusLuck:
            params = GameRule.configs.get("fusingParams")
            param_a = params.get("plusLuckInheritParamA", 1)
            param_b = params.get("plusLuckInheritParamB", 0)
            if self.is_same_series(eater):
                param_b += 1
            return param_a * param_b * self.plusLuck
        return 0

    def _level_up_xp(self):
        self._do_load()
        max_l = self._type.maxLevel
        params = GameRule.configs.get("creatureLevelParams")
        l_exponent = params.get("levelExponent", 1.45)
        l_scale = params.get("levelScale", 4.75)
        star_scale = params.get("starRankScale", 1)
        xp_incr = params.get("xpIncrementPerLevel", 300)
        return int(l_scale * max_l * star_scale *
                   math.pow(self.level, l_exponent) + xp_incr * self.level)

    def level_up(self, xp):
        self._do_load()
        self.xp += xp
        next_level = self.level + 1
        level_up_xp = self._level_up_xp()
        while self.xp > level_up_xp and next_level <= self._type.maxLevel:
            self.xp -= level_up_xp
            self.level = next_level
            level_up_xp = self._level_up_xp()
            next_level += 1

    def support_evolve(self):
        self._do_load()
        return bool(self._type.evolutionSlug)

    def evolution_materials(self):
        evolve_config = self._get_evolve_config()
        materials = evolve_config.get("non_element")
        ele_ms = evolve_config.get(self._type.element)
        if ele_ms:
            materials.update(ele_ms)
        return materials

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

#TODO: figure out how to deal with the class below
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