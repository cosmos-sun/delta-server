#!/usr/bin/python

import os, sys,random
from utils import protocol_pb2 as proto

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import content
from base_actor import ChildActor
from configs.world import World
from models.creature import CreatureTeam
from models.creature import CreatureInstance
from models.player import Player
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
        self.mockup=True

    def RetrieveWorld(self,msg):
        return self.resp(World.getWorld())

        # change to use this when content is stable
        #return self.resp(content.content.world)

    def RetrieveCreatureType(self,msg):
        return self.resp(World.getCreatureTypes())

        # change to use this when content is stable
        #rep = RetrieveCreatureTypeRep()
        #rep.creatures.extend(content.content.creature_types)
        #return self.resp(rep)

        rep = proto.BattleBeginRep()
        if self.mockup:
            rep.DungeonId=100
            waves=2
            for i in range(waves):
                w=World.getWave(100,100,'wave_'+str(i))
                wave=rep.Waves.add()
                wave.CopyFrom(w)
        else:
            #TODO: 1. verify the requirment for zone, area, dungeon
            #TODO: 2. random value for reward and store, waiting fo design
            rep.reward = \
                content.world[msg.zoneSlug][msg.areaSlug][msg.dungeonSlug].reward
        return self.resp(rep)

    def BattleEnd(self, msg):
        rep = proto.BattleEndRep()
        if self.mockup:
            rep.xp=msg.score/2
        else:
            #TODO: give the reward to player
            if msg.win:
                pass
            else:
                pass
            rep.result_code = proto.ResultCode.Value('SUCCESS')
        return self.resp(rep)

    def EditTeam(self, msg):
        CreatureTeam.store_from_proto(self.parent.pid, msg.teams)
        rep = proto.SimpleResponse()
        rep.result_code = proto.ResultCode.Value('SUCCESS')
        return self.resp(rep)

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
        player = Player(id=player_id).load()
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
        feeder_cids = []
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
            feeder_xp += f_c.fuse_trans_xp()
            # TODO - plusLuck

        # TODO - save player & level_up & remove_feeder in one transaction.
        # do fuse
        log_data = {"old_level": target_c.level,
                    "old_xp": target_c.xp}
        target_c.level_up(feeder_xp)
        player.store()
        log_data.update({"new_level": target_c.level,
                         "new_xp": target_c.xp})
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
        resp.result_code = FuseResultCode.Value("FUSE_SUCCESS")
        return self.resp(resp)

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
        player = Player(id=player_id).load()
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
        player = Player(id=player_id).load()
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
                 (player_id, old_slug, target_c.slug, str(feeder_map),
                  ascend_currency))
        resp.new_creature.CopyFrom(target_c.to_proto_class())
        resp.result_code = AscendResultCode.Value("ASCEND_SUCCESS")
        return self.resp(resp)

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
        player = Player(id=player_id).load()
        active_creatures = player.get_active_creatures()
        if on_sale_c.c_id in active_creatures:
            resp.result_code = SellCreatureResultCode.Value(
                "SELL_TARGET_IN_USE")

        sale_price = on_sale_c.sale_price()
        player.coins += sale_price

        # TODO - delete & save player in one transaction
        player.store()
        on_sale_c.delete()
        log.info("Player(%s) sold creature(id:%s, slug:%s) earned %s coins" %
                 (player_id, on_sale_c.c_id, on_sale_c.slug, sale_price))

        resp.result_code = SellCreatureResultCode.Value("SOLD_SUCCESS")
        return self.resp(resp)