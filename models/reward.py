import json
from dal.base import *
from models.player import Player
from models.content import GameRule, assign_value
from models.creature import CreatureInstance
from utils import protocol_pb2 as proto


class BattleReward(Base):
    _oid_key = "player_id"

    player_id = IntAttr()
    xp = IntAttr()
    coins = IntAttr()
    eggs = ListAttr(TextAttr())
    _speed_egg = TextAttr()
    progress = IntAttr()

    def add_egg(self, egg, egg_data, speed=False):
        assign_value(egg, egg_data)
        self.eggs = self.eggs or []
        if speed:
            self._speed_egg = json.dumps(egg_data)
        else:
            self.eggs.append(json.dumps(egg_data))

    def wave_egg(self, enemy, rep, boss=False):
        ratio = GameRule.battle_boss_egg_ratio \
                if boss else GameRule.battle_enemy_egg_ratio
        if not GameRule.true_from_ratio(ratio):
            return
        element = proto.Element.Name(GameRule.creature_types[enemy.slug].element)
        egg_data =  GameRule.battle_drop_egg(enemy, [element])
        if boss:
            egg = rep.boss_egg
        else:
            egg = rep.enemy_egg.add()
        self.add_egg(egg, egg_data)

    def get_xp(self, level=1):
        self.xp = GameRule.number_with_ratio(level * 50, GameRule.battle_reward_ratio, True)
        return self.xp

    def get_coins(self, level=1):
        self.coins = GameRule.number_with_ratio(level * 50, GameRule.battle_reward_ratio, True)
        return self.coins

    def clear_egg(self, dropper, elements, rep):
        egg_data =  GameRule.battle_drop_egg(dropper, elements)
        egg = rep.clear_egg
        self.add_egg(egg, egg_data)

    def speed_egg(self, dropper, elements, rep):
        egg_data =  GameRule.battle_drop_egg(dropper, elements)
        egg = rep.speed_egg
        self.add_egg(egg, egg_data, speed=True)

    def luck_egg(self, dropper, elements, pid, leader_id, rep):
        luck = CreatureInstance(c_id=leader_id, player_id=pid).load().plusLuck or 0
        if not GameRule.battle_drop_luck_egg(luck): return
        egg_data =  GameRule.battle_drop_egg(dropper, elements)
        egg = rep.luck_egg
        self.add_egg(egg, egg_data)

    def pay(self, speed):
        player = Player(id=self.player_id).load()
        coins = self.coins
        if speed:
            self.eggs.append(self._speed_egg)
        for egg in self.eggs:
            egg = json.loads(egg)
            if egg['type'] == GameRule.FAERIE_EGG or egg['type'] == GameRule.SELF_EGG:
                c_data = egg['creature']
                c = CreatureInstance(player_id=self.player_id).create(c_data['slug'],
                                              level=c_data.get('level', 1),
                                              xp=c_data.get('xp', 0),
                                              plusHP=c_data.get('plusHP', 0),
                                              plusAttack=c_data.get('plusAttack', 0),
                                              plusSpeed=c_data.get('plusSpeed', 0),
                                              plusLuck=c_data.get('plusLuck', 0),
                    )

                c.store()
            elif egg['type'] == GameRule.MATERIAL_EGG:
                m = egg.get('material')
                setattr(player, m, getattr(player, m) + 1)
            elif egg['type'] == GameRule.COIN_EGG:
                coins += egg.get('coins')
        player.set_progress(self.progress)
        player.add_xp(self.xp)
        player.coins += coins

        player.store()