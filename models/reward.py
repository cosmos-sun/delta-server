import simplejson
from dal.base import *
from models.player import Player, PassedDungeons
from models.content import GameRule
from models.creature import CreatureInstance
from utils import protocol_pb2 as proto
from utils.misc import assign_value


class BattleReward(Base):
    _oid_key = "player_id"

    player_id = IntAttr()
    xp = IntAttr()
    coins = IntAttr()
    dungeon_reward = TextAttr()
    eggs = ListAttr(TextAttr())
    _speed_eggs = ListAttr(TextAttr())
    _speed_turns = ListAttr(IntAttr())
    _dungeon_eggs = ListAttr(TextAttr())
    progress = IntAttr()
    dungeon_slug = TextAttr()
    key = LongAttr()

    def add_egg(self, egg, egg_data, speed=None, dungeon=False):
        assign_value(egg, egg_data)
        if not self.eggs: self.eggs = []
        if not self._speed_eggs: self._speed_eggs = []
        if not self._speed_turns: self._speed_turns = []
        if not self._dungeon_eggs: self._dungeon_eggs = []
        if speed:
            self._speed_eggs.append(simplejson.dumps(egg_data))
            self._speed_turns.append(speed)
        elif dungeon:
            self._dungeon_eggs.append(simplejson.dumps(egg_data))
        else:
            self.eggs.append(simplejson.dumps(egg_data))

    def drop_egg(self, droppers, config, rep, repeated=False, speed=False, dungeon_reward=False):
        egg_data =  GameRule.battle_drop_egg(droppers, config, dungeon_reward)
        if not egg_data: return
        egg = rep.add() if repeated else rep
        self.add_egg(egg, egg_data, speed=speed, dungeon=dungeon_reward)

    def drop_clearance_egg(self, droppers, configs, rep, repeated=False, speed=False):
        number = GameRule.random_from_number(configs['total'])
        index = 0
        for i in range(len(configs['rates'])):
            if configs['rates'][i] >= number:
                index = i
                break
        config = configs['loots'][index]
        self.drop_egg(droppers, config, rep, repeated=repeated, speed=speed)

    def drop_luck_egg(self, dropper, configs, pid, leader_id, rep):
        luck = CreatureInstance(cid=leader_id, player_id=pid).load().plusLuck or 0
        if not GameRule.battle_drop_luck_egg(luck): return
        self.drop_clearance_egg(dropper, configs, rep)

    def drop_speed_egg(self, dropper, configs, speed_configs, rep):
        if not speed_configs: return
        for i in range(len(speed_configs)):
            speed_egg = rep.add()
            speed_egg.param.append(speed_configs[i])
            egg = speed_egg.egg.add()
            self.drop_clearance_egg(dropper, configs, egg, speed=speed_configs[i])

    def drop_dungeon_egg(self, configs, rep):
        #TODO: discuss if we need check passed_dungeons when battle begin or not
        passed_dungeons = PassedDungeons(player_id=self.player_id).load().slugs or []
        if self.dungeon_slug in passed_dungeons: return
        for config in configs:
            self.drop_egg('', config, rep, repeated=True, dungeon_reward=True)

    def calc_speed_eggs(self, turns):
        if not turns: return
        for i in sorted(self._speed_turns, reverse=True):
            if turns <= i and self._speed_eggs:
                self.eggs.append(self._speed_eggs.pop(0))
            else:
                break

    def pay(self, speed_turns):
        pay_data = {'drops':[]}
        player = Player(id=self.player_id).load()
        passed_dungeons = PassedDungeons(player_id=self.player_id).load()
        if not passed_dungeons.slugs: passed_dungeons.slugs = []
        if self.dungeon_slug not in passed_dungeons.slugs:
            passed_dungeons.slugs.append(self.dungeon_slug)
            passed_dungeons.store()
            self.eggs.extend(self._dungeon_eggs)
        coins = self.coins
        gems = 0
        self.calc_speed_eggs(speed_turns)
        for egg in self.eggs:
            egg = simplejson.loads(egg)
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
                pay_data['drops'].append({'type': egg['type'], 'slug': c_data['slug']})
            elif egg['type'] == GameRule.MATERIAL_EGG:
                m = egg.get('material')
                setattr(player, m, getattr(player, m) + 1)
                pay_data['drops'].append({'type': egg['type'], 'slug': m})
            elif egg['type'] == GameRule.COIN_EGG:
                coins += egg.get('coins')
            elif egg['type'] == GameRule.GEM_EGG:
                gems += egg.get('gems')
        player.set_progress(self.progress)
        player.add_xp(self.xp)
        player.coins += coins
        player.gems += gems

        pay_data['xp'] = self.xp
        pay_data['coins'] = self.coins
        pay_data['gems'] = gems

        player.store()
        return pay_data, player