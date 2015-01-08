#!/usr/bin/python

import os, sys, time
from utils import protocol_pb2 as proto

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.content import GameRule
from base_actor import ChildActor
from base_actor import MessageHandlerWrapper
from configs.world import World
from models.reward import BattleReward
from models.content import GameRule
from models.creature import CreatureTeam
from models.creature import CreatureInstance
from utils.protocol_pb2 import AddEnergyRep
from utils.protocol_pb2 import AddEnergyResultCode
from utils.protocol_pb2 import AscendRep
from utils.protocol_pb2 import AscendResultCode
from utils.protocol_pb2 import BuyCreatureSpaceRep
from utils.protocol_pb2 import BuyCreatureSpaceResultCode
from utils.protocol_pb2 import ConvertMaterialRep
from utils.protocol_pb2 import ConvertMaterialResultCode
from utils.protocol_pb2 import EvolveRep
from utils.protocol_pb2 import EvolveResultCode
from utils.protocol_pb2 import FuseRep
from utils.protocol_pb2 import FuseResultCode
from utils.protocol_pb2 import SellCreatureRep
from utils.protocol_pb2 import SellCreatureResultCode
from utils import log
from utils.misc import assign_value
from stats import DeltaBattleBegin, DeltaBattleEnd, DeltaEditTeam, DeltaFuse,\
                  DeltaEvolve, DeltaSellCreature, DeltaGacha, DeltaAddEnergy,\
                  DeltaConvertMaterial, DeltaBuyCreatureSpace, DeltaRevenueIAP,\
                  DeltaRevenueIAB

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
        def get_battle_key():
            return int(time.time() * 1000000)
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
            event_data = {'player':{'session': self.parent.session_id}}
            dungeon = GameRule.dungeons[msg.dungeonSlug]
            if player.get_energy() < dungeon['requirement']['energy']:
                rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_FAIL_ENERGY')
                return self.resp(rep)
            if player.progress < dungeon['requirement']['progress']:
                rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_FAIL_PROGRESS')
                return self.resp(rep)
            last_boss = []
            #if there is a reward already, overwrite it
            battle_reward = BattleReward(player_id=pid)
            battle_reward.progress = dungeon['reward']['progress']
            battle_reward.dungeon_slug = msg.dungeonSlug
            # get enemies and bosses
            enemies = []
            for wave in dungeon['waves']:
                for enemy in wave['enemies']:
                    enemies.append(enemy)
                if wave['boss'] and wave['boss']['slug'] != "":
                    enemies.append(wave['boss'])
                    last_boss.append(wave['boss'])
            if last_boss:
                # if have last boss, remove it from enemies list
                enemies = enemies[:-1]
            ## generate battle end reward
            rep.xp = dungeon['reward']['xp']
            rep.coins = dungeon['reward']['softCurrency']
            battle_reward.xp = rep.xp
            battle_reward.coins = rep.coins
            for egg in dungeon['reward']['eggs_enemy']:
                battle_reward.drop_egg(enemies, egg, rep.enemy_egg, repeated=True)
            for egg in dungeon['reward']['eggs_boss']:
                battle_reward.drop_egg(last_boss, egg, rep.boss_egg, repeated=True)

            battle_reward.drop_clearance_egg(last_boss, dungeon['reward']['eggs_clearance'], rep.clear_egg)
            battle_reward.drop_speed_egg(last_boss, dungeon['reward']['eggs_clearance'], dungeon['speed_clearance'], rep.speed_egg)
            battle_reward.drop_luck_egg(last_boss, dungeon['reward']['eggs_clearance'], pid, msg.leader_id, rep.luck_egg)
            battle_reward.drop_dungeon_egg(dungeon['reward']['eggs_map'], rep.dungeon_egg)
            if not player.spend_energy(dungeon['requirement']['energy'], do_store=True):
                rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_FAIL_ENERGY')
                return self.resp(rep)
            battle_key = get_battle_key()
            battle_reward.key = battle_key
            battle_reward.store()
            rep.battle_key = battle_key

            event_data['zone'] = msg.zoneSlug
            event_data['area'] = msg.areaSlug
            event_data['dungeon'] = msg.dungeonSlug
            event_data['battle_key'] = battle_key
            self.send_event(DeltaBattleBegin, event_data, player)

        rep.result_code = proto.BattleBeginRepResultCode.Value('BATTLE_BEGIN_SUCCESS')
        return self.resp(rep)

    @MessageHandlerWrapper(proto.BattleBeginRep,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def BattleEnd(self, msg):
        rep = proto.BattleEndRep()
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
            'zone': msg.zoneSlug,
            'area': msg.areaSlug,
            'dungeon': msg.dungeonSlug,
            'battle_key': msg.battle_key,
            'turns': msg.turns,
            #TODO: add active team to battle end messge, 'team':[]
        }
        player = None
        if self.mockup:
            rep.xp=msg.score/2
        else:
            reward = BattleReward(player_id=self.parent.pid).load()
            if reward.player_id is None or reward.dungeon_slug != msg.dungeonSlug: #TODO change check dungeonslug to check battle_key
                rep.result_code = proto.ResultCode.Value("FAILED")
                event_data['result_code'] = "NOT_FOUND"
                self.send_event(DeltaBattleEnd, event_data)
                return self.resp(rep)
            if msg.win:
                pay_data, player = reward.pay(msg.turns)
                rep.result_code = proto.ResultCode.Value('SUCCESS')
                event_data['result_code'] = 'SUCCESS'
                event_data.update(pay_data)
            else:
                rep.result_code = proto.ResultCode.Value('FAILED')
                event_data['result_code'] = "FAILED"
            reward.delete()

            self.send_event(DeltaBattleEnd, event_data, player)
        return self.resp(rep)

    @MessageHandlerWrapper(proto.SimpleResponse,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def EditTeam(self, msg):
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
        }
        teams = CreatureTeam.store_from_proto(self.parent.pid, msg.teams)
        rep = proto.SimpleResponse()
        rep.result_code = proto.ResultCode.Value('SUCCESS')

        event_data['teams'] = teams
        self.send_event(DeltaEditTeam, event_data)
        return self.resp(rep)

    @MessageHandlerWrapper(FuseRep,
                           FuseResultCode.Value("FUSE_INVALID_SESSION"))
    def Fuse(self, msg):
        log.info("Fuse %s" % msg)
        resp = FuseRep()
        player_id = self.parent.pid
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
            'feeds': []
        }
        # verify target
        if not msg.target:
            resp.result_code = FuseResultCode.Value("FUSE_MISSING_TARGET")
            return self.resp(resp)
        target_c = CreatureInstance(player_id=player_id, cid=msg.target.cid)
        if not target_c.exist():
            resp.result_code = FuseResultCode.Value("FUSE_TARGET_NOT_EXIST")
            return self.resp(resp)
        event_data['creature_before'] = target_c.get_stats_data()
        player = self.parent.player

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
            if f.cid == target_c.cid:
                resp.result_code = FuseResultCode.Value("FUSE_FEEDER_SELF")
                return self.resp(resp)
            f_c = CreatureInstance(player_id=player_id, cid=f.cid)
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

            event_data['feeds'].append(f.get_stats_data())

        # verify coins
        fuse_currency = target_c.fuse_currency() * len(feeder_cids)
        if player.coins < fuse_currency:
            resp.result_code = FuseResultCode.Value("FUSE_NOT_ENOUGH_COINS")
            resp.lack_coins = fuse_currency - player.coins
            return self.resp(resp)
        player.coins -= fuse_currency

        got_mega = target_c.fuse_mega_odds(same_element_num, len(feeder_cids))
        mega_factor = GameRule.fuse_mega_factor
        if got_mega:
            feeder_xp *= mega_factor
            feeder_plus_hp *= mega_factor
            feeder_plus_attack *= mega_factor
            feeder_plus_speed *= mega_factor
            feeder_plus_luck *= mega_factor
            event_data['mega_factor'] = mega_factor

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
            fc = CreatureInstance(player_id=player_id, cid=f_cid)
            fc.delete()
            log.info("Player(%s) delete creature(%s slug:%s) to fuse "
                     "creature(cid:%s slug:%s)" %
                     (player_id, f_cid, fc.slug, target_c.cid, target_c.slug))
        log.info("Player(%s) cost %s coins to fuse creature(cid:%s, slug:%s): "
                 "%s" % (player_id, fuse_currency, target_c.cid,
                         target_c.slug, str(log_data)))
        resp.updated_creature.CopyFrom(target_c.to_proto_class())
        resp.got_mega = got_mega

        event_data['creature_after'] = target_c.get_stats_data()
        event_data['same_element_num'] = same_element_num
        event_data['coins_cost'] = fuse_currency
        self.send_event(DeltaFuse, event_data)
        resp.result_code = FuseResultCode.Value("FUSE_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(EvolveRep,
                           EvolveResultCode.Value("EVOLVE_INVALID_SESSION"))
    def Evolve(self, msg):
        log.info("Evolve %s" % msg)
        resp = EvolveRep()
        player_id = self.parent.pid
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
        }
        # verify target
        if not msg.target:
            resp.result_code = EvolveResultCode.Value("EVOLVE_MISSING_TARGET")
            return self.resp(resp)
        target_c = CreatureInstance(player_id=player_id, cid=msg.target.cid)
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
        event_data['creature_before'] = target_c.get_stats_data()
        # verify coins
        player = self.parent.player
        evolve_currency = target_c.evolve_currency()
        if player.coins < evolve_currency:
            resp.result_code = EvolveResultCode.Value(
                "EVOLVE_NOT_ENOUGH_COINS")
            resp.lack_coins = evolve_currency - player.coins
            return self.resp(resp)
        player.coins -= evolve_currency
        event_data['coins_cost'] = evolve_currency

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

        event_data['creature_after'] = target_c.get_stats_data()
        self.send_event(DeltaEvolve, event_data, player)
        resp.result_code = EvolveResultCode.Value("EVOLVE_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(AscendRep,
                           AscendResultCode.Value("ASCEND_INVALID_SESSION"))
    def Ascend(self, msg):
        #TODO: add stats events when implement this
        log.info("Ascend %s" % msg)
        resp = AscendRep()
        player_id = self.parent.pid

        # verify target
        if not msg.target:
            resp.result_code = AscendResultCode.Value("ASCEND_MISSING_TARGET")
            return self.resp(msg)
        target_c = CreatureInstance(player_id=player_id, cid=msg.target.cid)
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
            if f.cid == target_c.cid:
                # skip self
                continue
            if f.cid in active_creatures:
                # skip active creatures
                continue
            if required_creatures.get(f.slug, 0) > 0:
                # find one feeder, record it and reduce the requirement.
                feeder_cids.append(f.cid)
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
            fc = CreatureInstance(player_id=player_id, cid=f_cid)
            fc.delete()
            log.info("Player(%s) delete creature(%s slug:%s) to ascend "
                     "creature(cid:%s slug:%s)" %
                     (player_id, f_cid, fc.slug, target_c.cid, target_c.slug))
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
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
        }
        # verify target
        if not msg.target:
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_MISSING_TARGET")
            return self.resp(resp)
        on_sale_c = CreatureInstance(player_id=player_id, cid=msg.target.cid)
        if not on_sale_c.exist():
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_TARGET_NOT_EXIST")
            return self.resp(resp)
        player = self.parent.player
        active_creatures = player.get_active_creatures()
        if on_sale_c.cid in active_creatures:
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_TARGET_IN_USE")
            return self.resp(resp)

        sale_price = on_sale_c.sale_price()
        player.coins += sale_price
        resp.coins = sale_price

        event_data['creature'] = on_sale_c.get_stats_data()
        event_data['coins'] = sale_price
        # TODO - delete & save player in one transaction
        player.store()
        on_sale_c.delete()
        log.info("Player(%s) sold creature(id:%s, slug:%s) earned %s coins" %
                 (player_id, on_sale_c.cid, on_sale_c.slug, sale_price))

        self.send_event(DeltaSellCreature, event_data, player)
        resp.result_code = SellCreatureResultCode.Value("SOLD_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(proto.GachaShakeRep,
                           proto.ResultCode.Value("INVALID_SESSION"))
    def GachaShake(self, msg):
        rep = proto.GachaShakeRep()
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
        }
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
        event_data['creature'] = c.get_stats_data()
        self.send_event(DeltaGacha, event_data)
        rep.result_code = proto.ResultCode.Value("SUCCESS")
        return self.resp(rep)

    @MessageHandlerWrapper(AddEnergyRep, AddEnergyResultCode.Value(
        "ADD_ENERGY_INVALID_SESSION"))
    def AddEnergy(self, msg):
        resp = AddEnergyRep()
        event_data = {
            'player':{'session': self.parent.session_id,
                      'id': self.parent.pid},
        }
        player = self.parent.player
        consume_gems = GameRule.energy_consume_gems
        if player.gems < consume_gems:
            resp.result_code = AddEnergyResultCode.Value(
                "ADD_ENERGY_NOT_ENOUGH_GEMS")
            return self.resp(resp)
        player.add_energy()
        player.gems -= consume_gems
        player.store()
        log.info("Player(%s) consume %s gems to buy %s energy" %
                 (player.id, consume_gems, player.get_max_energy()))
        event_data['gems_cost'] = consume_gems
        self.send_event(DeltaAddEnergy, event_data, player)
        resp.result_code = AddEnergyResultCode.Value("ADD_ENERGY_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(ConvertMaterialRep, ConvertMaterialResultCode.Value(
        "CONVERT_INVALID_SESSION"))
    def ConvertMaterial(self, msg):
        resp = ConvertMaterialRep()
        f_m = msg.from_slug
        t_m = msg.to_slug
        amount = msg.amount
        if not f_m:
            resp.result_code = ConvertMaterialResultCode.Value(
                "CONVERT_MISSING_FROM")
        elif not t_m:
            resp.result_code = ConvertMaterialResultCode.Value(
                "CONVERT_MISSING_TO")
        elif not amount:
            resp.result_code = ConvertMaterialResultCode.Value(
                "CONVERT_MISSING_AMOUNT")
        else:
            convert_info = GameRule.material_conversion.get(t_m)
            rate = convert_info and convert_info.get(f_m)
            if not rate:
                resp.result_code = ConvertMaterialResultCode.Value(
                    "CONVERT_NOT_ALLOWED")
            else:
                f_m_required = rate * amount
                player = self.parent.player
                if f_m_required > getattr(player, f_m):
                    resp.result_code = ConvertMaterialResultCode.Value(
                        "CONVERT_NOT_ENOUGH_MATERIAL")
                else:
                    player.modify_material(f_m, -f_m_required)
                    player.modify_material(t_m, amount)
                    player.store()
                    log.info("Player(%s) convert %s(%s) to %s(%s)" %
                             (player.id, f_m, f_m_required, t_m, amount))
                    resp.result_code = ConvertMaterialResultCode.Value(
                        "CONVERT_SUCCESS")
        return self.resp(resp)

    @MessageHandlerWrapper(BuyCreatureSpaceRep,
                           BuyCreatureSpaceResultCode.Value(
                               "BUY_CREATURE_SPACE_INVALID_SESSION"))
    def BuyCreatureSpace(self, msg):
        resp = BuyCreatureSpaceRep()
        player = self.parent.player
        consume_gems = GameRule.creature_space_consume_gems
        if player.gems < consume_gems:
            resp.result_code = BuyCreatureSpaceResultCode.Value(
                "BUY_CREATURE_SPACE_NOT_ENOUGH_GEMS")
        else:
            player.buy_creature_space()
            player.gems -= consume_gems
            player.store()
            log.info("Player(%s) consume %s gems to extend %s creature space."
                     % (player.id, consume_gems,
                        GameRule.extend_creature_space))
            resp.result_code = BuyCreatureSpaceResultCode.Value(
                "BUY_CREATURE_SPACE_SUCCESS")
        return self.resp(resp)
