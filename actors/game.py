#!/usr/bin/python

import os, sys,random
from utils import protocol_pb2 as proto

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.content import GameRule, assign_value
from base_actor import ChildActor
from base_actor import MessageHandlerWrapper
from configs.world import World
from models.reward import BattleReward
from models.creature import CreatureTeam
from models.creature import CreatureInstance
from models.player import Player
from utils.protocol_pb2 import AddEnergyRep
from utils.protocol_pb2 import AddEnergyResultCode
from utils.protocol_pb2 import AscendRep
from utils.protocol_pb2 import AscendResultCode
from utils.protocol_pb2 import EvolveRep
from utils.protocol_pb2 import EvolveResultCode
from utils.protocol_pb2 import FuseRep
from utils.protocol_pb2 import FuseResultCode
from utils.protocol_pb2 import SellCreatureRep
from utils.protocol_pb2 import SellCreatureResultCode
from utils import log


class Game(ChildActor):
    def __init__(self, parent):
        super(Game, self).__init__(parent)
        self.mockup=False

    # ======================
    # content
    # ======================
    def RetrieveWorld(self, msg):
        if self.mockup:
            return self.resp(World.getWorld())
        return self.resp(GameRule.world_proto)

    def RetrieveCreatureType(self, msg):
        if self.mockup:
            return self.resp(World.getCreatureTypes())
        rep = proto.RetrieveCreatureTypeRep()
        rep.creatures.extend(GameRule.creature_types_proto)
        return self.resp(rep)

    def GetGlobalConfigs(self, msg):
        return self.resp(GameRule.configs_proto)

    def GachaTrees(self, msg):
        rep = proto.GachaTreesRep()
        rep.tree_slugs.extend(GameRule.gacha_list.keys())
        return self.resp(rep)

    @MessageHandlerWrapper(proto.BattleBeginRep,
                           proto.BattleBeginRepResultCode.Value("BATTLE_BEGIN_INVALID_SESSION"))
    def BattleBegin(self, msg):
        rep = proto.BattleBeginRep()
        if self.mockup:
            rep.DungeonId=100
            waves=2
            for i in range(waves):
                w=World.getWave(100,100,'wave_'+str(i))
                wave=rep.Waves.add()
                wave.CopyFrom(w)
        else:
            pid = self.parent.pid
            player = self.parent.player
            dungeon = GameRule.dungeons[msg.dungeonSlug]
            success = player.spend_energy(dungeon.requirement.energy)
            if not success:
                rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_FAIL_ENERGY')
                return self.resp(rep)
            #TODO: verify the requirement for zone, area
            if player.progress < dungeon.requirement.progress:
                rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_FAIL_PROGRESS')
                return self.resp(rep)
            boss_dropped = False
            last_boss = None
            #if there is a reward already, overwrite it
            battle_reward = BattleReward(player_id=pid)
            battle_reward.progress = dungeon.reward.progress
            # add eggs into wave enemies
            for wave in dungeon.waves:
                #do we need to add wave drop into final reward
                for enemy in wave.enemies:
                    battle_reward.wave_egg(enemy, rep)
                if wave.boss and wave.boss.slug != "" and not boss_dropped:
                    boss_dropped = True
                    last_boss = wave.boss
                    battle_reward.wave_egg(wave.boss, rep, boss=True)
            ## generate battle end reward
            rep.xp = battle_reward.get_xp(last_boss.level)
            rep.coins = battle_reward.get_coins(last_boss.level)
            battle_reward.clear_egg(last_boss, dungeon.elements, rep)
            battle_reward.speed_egg(last_boss, dungeon.elements, rep)
            battle_reward.luck_egg(last_boss, dungeon.elements, pid, msg.leader_id, rep)
            battle_reward.store()

        rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_SUCCESS')
        return self.resp(rep)

    @MessageHandlerWrapper(proto.BattleBeginRep,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def BattleEnd(self, msg):
        rep = proto.BattleEndRep()
        if self.mockup:
            rep.xp=msg.score/2
        else:
            reward = BattleReward(player_id=self.parent.pid).load()
            if reward.player_id is None:
                rep.result_code = proto.ResultCode.Value("FAILED")
                return self.resp(rep)
            if msg.win:
                reward.pay(msg.speed)
                rep.result_code = proto.ResultCode.Value('SUCCESS')
            else:
                rep.result_code = proto.ResultCode.Value('FAILED')
            #reward.delete()
        return self.resp(rep)

    @MessageHandlerWrapper(proto.SimpleResponse,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def EditTeam(self, msg):
        CreatureTeam.store_from_proto(self.parent.pid, msg.teams)
        rep = proto.SimpleResponse()
        rep.result_code = proto.ResultCode.Value('SUCCESS')
        return self.resp(rep)

    @MessageHandlerWrapper(FuseRep,
                           FuseResultCode.Value("FUSE_INVALID_SESSION"))
    def Fuse(self, msg):
        log.info("Fuse %s" % msg)
        resp = FuseRep()
        player_id = self.parent.pid

        # verify target
        if not msg.target:
            resp.result_code = FuseResultCode.Value("FUSE_MISSING_TARGET")
            return self.resp(resp)
        target_c = CreatureInstance(player_id=player_id, c_id=msg.target.cid)
        if not target_c.exist():
            resp.result_code = FuseResultCode.Value("FUSE_TARGET_NOT_EXIST")
            return self.resp(resp)

        # verify coins
        player = self.parent.player
        fuse_currency = target_c.fuse_currency()
        if player.coins < fuse_currency:
            resp.result_code = FuseResultCode.Value("FUSE_NOT_ENOUGH_COINS")
            resp.lack_coins = fuse_currency - player.coins
            return self.resp(resp)
        player.coins -= fuse_currency

        # verify feeders
        feeders = msg.feeders
        if not feeders:
            resp.result_code = FuseResultCode.Value("FUSE_NO_FEEDERS")
            return self.resp(resp)
        feeder_xp = 0
        feeder_plus_hp = 0
        feeder_plus_attack = 0
        feeder_plus_speed = 0
        feeder_plus_luck = 0
        feeder_cids = []
        same_element_num = 0
        active_creatures = player.get_active_creatures()
        for f in feeders:
            if f.cid in feeder_cids:
                # skip duplicate feeders
                continue
            if f.cid == target_c.c_id:
                resp.result_code = FuseResultCode.Value("FUSE_FEEDER_SELF")
                return self.resp(resp)
            f_c = CreatureInstance(player_id=player_id, c_id=f.cid)
            if not f_c.exist():
                resp.result_code = FuseResultCode.Value(
                    "FUSE_FEEDER_NOT_EXIST")
                return self.resp(resp)
            if f.cid in active_creatures:
                resp.result_code = FuseResultCode.Value("FUSE_FEEDER_IN_USE")
                return self.resp(resp)
            feeder_cids.append(f.cid)
            if f_c.is_same_element(target_c):
                same_element_num += 1
            feeder_xp += f_c.fuse_trans_xp(target_c)
            feeder_plus_hp += f_c.fuse_plus_hp(target_c)
            feeder_plus_attack += f_c.fuse_plus_attack(target_c)
            feeder_plus_speed += f_c.fuse_plus_speed(target_c)
            feeder_plus_luck += f_c.fuse_plus_luck(target_c)

        got_mega = target_c.fuse_mega_odds(same_element_num, len(feeder_cids))
        # TODO - move factor to config
        MEGA_FACTOR = 2
        if got_mega:
            feeder_xp *= MEGA_FACTOR
            feeder_plus_hp *= MEGA_FACTOR
            feeder_plus_attack *= MEGA_FACTOR
            feeder_plus_speed *= MEGA_FACTOR
            feeder_plus_luck *= MEGA_FACTOR

        # TODO - save player & level_up & remove_feeder in one transaction.
        # do fuse
        log_data = {"old_level": target_c.level,
                    "old_xp": target_c.xp,
                    "old_plus_hp": target_c.plusHP,
                    "old_plus_attack": target_c.plusAttack,
                    "old_plus_speed": target_c.plusSpeed,
                    "old_plus_luck": target_c.plusLuck}
        target_c.level_up(feeder_xp)
        target_c.plusHP += feeder_plus_hp
        target_c.plusAttack += feeder_plus_attack
        target_c.plusSpeed += feeder_plus_speed
        target_c.plusLuck += feeder_plus_luck
        target_c.store()
        player.store()
        log_data.update({"new_level": target_c.level,
                         "new_xp": target_c.xp,
                         "new_plus_hp": target_c.plusHP,
                         "new_plus_attack": target_c.plusAttack,
                         "new_plus_speed": target_c.plusSpeed,
                         "new_plus_luck": target_c.plusLuck})
        for f_cid in feeder_cids:
            fc = CreatureInstance(player_id=player_id, c_id=f_cid)
            fc.delete()
            log.info("Player(%s) delete creature(%s slug:%s) to fuse "
                     "creature(cid:%s slug:%s)" %
                     (player_id, f_cid, fc.slug, target_c.c_id, target_c.slug))
        log.info("Player(%s) cost %s coins to fuse creature(cid:%s, slug:%s): "
                 "%s" % (player_id, fuse_currency, target_c.c_id,
                         target_c.slug, str(log_data)))
        resp.updated_creature.CopyFrom(target_c.to_proto_class())
        resp.got_mega = got_mega
        resp.result_code = FuseResultCode.Value("FUSE_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(EvolveRep,
                           EvolveResultCode.Value("EVOLVE_INVALID_SESSION"))
    def Evolve(self, msg):
        log.info("Evolve %s" % msg)
        resp = EvolveRep()
        player_id = self.parent.pid

        # verify target
        if not msg.target:
            resp.result_code = EvolveResultCode.Value("EVOLVE_MISSING_TARGET")
            return self.resp(resp)
        target_c = CreatureInstance(player_id=player_id, c_id=msg.target.cid)
        if not target_c.exist():
            resp.result_code = EvolveResultCode.Value(
                "EVOLVE_TARGET_NOT_EXIST")
            return self.resp(resp)
        if not target_c.is_max_level():
            resp.result_code = EvolveResultCode.Value(
                "EVOLVE_LEVEL_UNSATISFIED")
            return self.resp(resp)
        if not target_c.support_evolve():
            resp.result_code = EvolveResultCode.Value("EVOLVE_DISABLE")
            return self.resp(resp)

        # verify coins
        player = self.parent.player
        evolve_currency = target_c.evolve_currency()
        if player.coins < evolve_currency:
            resp.result_code = EvolveResultCode.Value(
                "EVOLVE_NOT_ENOUGH_COINS")
            resp.lack_coins = evolve_currency - player.coins
            return self.resp(resp)
        player.coins -= evolve_currency

        # verify material
        material_req = target_c.evolution_materials()
        for material, amount in material_req.iteritems():
            own_amount = getattr(player, material)
            if own_amount < amount:
                resp.result_code = EvolveResultCode.Value(
                    "EVOLVE_LACK_MATERIAL")
                return self.resp(resp)
            setattr(player, material, own_amount - amount)

        # TODO - evolve_creature & save player in one transaction.
        old_slug = target_c.slug
        target_c.evolve()
        player.store()
        log.info("Player(%s) evolve %s to %s, cost: %s and %s coins" %
                 (player_id, old_slug, target_c.slug, str(material_req),
                  evolve_currency))
        resp.new_creature.CopyFrom(target_c.to_proto_class())
        resp.result_code = EvolveResultCode.Value("EVOLVE_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(AscendRep,
                           AscendResultCode.Value("ASCEND_INVALID_SESSION"))
    def Ascend(self, msg):
        log.info("Ascend %s" % msg)
        resp = AscendRep()
        player_id = self.parent.pid

        # verify target
        if not msg.target:
            resp.result_code = AscendResultCode.Value("ASCEND_MISSING_TARGET")
            return self.resp(msg)
        target_c = CreatureInstance(player_id=player_id, c_id=msg.target.cid)
        if not target_c.exist():
            resp.result_code = AscendResultCode.Value(
                "ASCEND_TARGET_NOT_EXIST")
            return self.resp(resp)
        if not target_c.is_max_level():
            resp.result_code = AscendResultCode.Value(
                "ASCEND_LEVEL_UNSATISFIED")
            return self.resp(resp)
        transcend = target_c.get_transcend()
        if not (transcend and transcend.transcendSlug
                and transcend.creatureAmount):
            resp.result_code = AscendResultCode.Value("ASCEND_DISABLE")
            return self.resp(resp)

        # verify coins
        player = self.parent.player
        ascend_currency = target_c.ascend_currency()
        if player.coins < ascend_currency:
            resp.result_code = AscendResultCode.Value(
                "ASCEND_NOT_ENOUGH_COINS")
            return self.resp(resp)
        player.coins -= ascend_currency

        # ascend required creatures map
        required_creatures = {}
        for req_feeder in transcend.creatureAmount:
            required_creatures[req_feeder.creatureSlug] = req_feeder.amount
        # feed from low level to high level.
        feeders = CreatureInstance.load_by_attribute("player_id", player_id)
        feeders = sorted(feeders, lambda x, y: cmp(x.level, y.level))
        feeder_cids = []
        used_creatures = []
        active_creatures = player.get_active_creatures()
        for f in feeders:
            if f.c_id == target_c.c_id:
                # skip self
                continue
            if f.cid in active_creatures:
                # skip active creatures
                continue
            if required_creatures.get(f.slug, 0) > 0:
                # find one feeder, record it and reduce the requirement.
                feeder_cids.append(f.c_id)
                required_creatures[f.slug] -= 1
                used_creatures.append(f.info())

                # TODO - Design: merge plugXXX?

        if required_creatures:
            # Didn't find all the required creatures.
            resp.result_code = AscendResultCode.Value("ASCEND_MISSING_FEEDER")
            return self.resp(resp)

        # TODO - save player & transcend & delete feeder in one transaction
        old_slug = target_c.slug
        target_c.transcend()
        player.store()
        for f_cid in feeder_cids:
            fc = CreatureInstance(player_id=player_id, c_id=f_cid)
            fc.delete()
            log.info("Player(%s) delete creature(%s slug:%s) to ascend "
                     "creature(cid:%s slug:%s)" %
                     (player_id, f_cid, fc.slug, target_c.c_id, target_c.slug))
        log.info("Player(%s) ascend %s to %s, cost: %s and %s coins" %
                 (player_id, old_slug, target_c.slug, str(used_creatures),
                  ascend_currency))
        resp.new_creature.CopyFrom(target_c.to_proto_class())
        resp.result_code = AscendResultCode.Value("ASCEND_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(SellCreatureRep, SellCreatureResultCode.Value(
        "SELL_INVALID_SESSION"))
    def SellCreature(self, msg):
        log.info("Sell creature: %s" % msg)
        resp = SellCreatureRep()
        player_id = self.parent.pid

        # verify target
        if not msg.target:
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_MISSING_TARGET")
            return self.resp(resp)
        on_sale_c = CreatureInstance(player_id=player_id, c_id=msg.target.cid)
        if not on_sale_c.exist():
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_TARGET_NOT_EXIST")
            return self.resp(resp)
        player = self.parent.player
        active_creatures = player.get_active_creatures()
        if on_sale_c.c_id in active_creatures:
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_TARGET_IN_USE")
            return self.resp(resp)

        sale_price = on_sale_c.sale_price()
        player.coins += sale_price
        resp.coins = sale_price

        # TODO - delete & save player in one transaction
        player.store()
        on_sale_c.delete()
        log.info("Player(%s) sold creature(id:%s, slug:%s) earned %s coins" %
                 (player_id, on_sale_c.c_id, on_sale_c.slug, sale_price))

        resp.result_code = SellCreatureResultCode.Value("SOLD_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(proto.GachaShakeRep,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def GachaShake(self, msg):
        rep = proto.GachaShakeRep()
        data = GameRule.gacha(msg.tree_slug)
        assign_value(rep.egg, data)

        c_data = data['creature']
        c = CreatureInstance(player_id=self.parent.pid).create(c_data['slug'],
                             level=c_data.get('level', 1),
                             xp=c_data.get('xp', 0),
                             plusHP=c_data.get('plusHP', 0),
                             plusAttack=c_data.get('plusAttack', 0),
                             plusSpeed=c_data.get('plusSpeed', 0),
                             plusLuck=c_data.get('plusLuck', 0),
                    )
        c.store()

        rep.result_code = proto.ResultCode.Value("SUCCESS")
        return self.resp(rep)

    @MessageHandlerWrapper(AddEnergyRep, AddEnergyResultCode.Value(
        "ADD_ENERGY_INVALID_SESSION"))
    def AddEnergy(self, msg):
        CONSUME_GEMS = 1  # TODO - Design
        resp = AddEnergyRep()
        player = self.parent.player
        if player.gems < CONSUME_GEMS:
            resp.result_code = AddEnergyResultCode.Value(
                "ADD_ENERGY_NOT_ENOUGH_GEMS")
            return self.resp(resp)
        player.add_energy()
        player.gems -= CONSUME_GEMS
        player.store()
        resp.result_code = AddEnergyResultCode.Value("ADD_ENERGY_SUCCESS")
        return self.resp(resp)
