from dal.base import *
from models.content import GameRule
from models.creature import CreatureInstance
from models.creature import Egg
from utils import protocol_pb2 as proto


class BattleReward(Base):
    _oid_key = "player_id"

    player_id = IntAttr()
    xp = IntAttr()
    eggs = ListAttr(TextAttr())

    def wave_egg(self, enemy, elements, boss=False):
        result = GameRule.battle_wave_egg(enemy, elements, boss)
        if not result: return
        kind, data = result
        egg = Egg.create_proto_egg(kind, data)
        self.eggs.append(egg.SerializeToString())
        enemy.egg.CopyFrom(egg)

    def get_xp(self, level):
        self.xp = GameRule.battle_xp(level)
        return self.xp

    def clear_egg(self, dropper, elements, rep):
        result = GameRule.battle_drop_egg(dropper, elements)
        if not result: return
        kind, data = result
        egg = Egg.create_proto_egg(kind, data)
        self.eggs.append(egg.SerializeToString())
        rep.clear_egg.CopyFrom(egg)

    def speed_egg(self, dropper, elements, rep):
        result = GameRule.battle_drop_egg(dropper, elements)
        if not result: return
        kind, data = result
        egg = Egg.create_proto_egg(kind, data)
        self.eggs.append(egg.SerializeToString())
        rep.speed_egg.CopyFrom(egg)

    def luck_egg(self, dropper, elements, pid, leader_id, rep):
        luck = CreatureInstance(c_id=leader_id, player_id=pid).load().plusLuck or 0
        if not GameRule.battle_drop_luck_egg(luck): return
        result = GameRule.battle_drop_egg(dropper, elements)
        if not result: return
        kind, data = result
        egg = Egg.create_proto_egg(kind, data)
        self.eggs.append(egg.SerializeToString())
        rep.speed_egg.CopyFrom(egg)

    def pay(self, speed):
        #TODO: give reward to player
        pass
