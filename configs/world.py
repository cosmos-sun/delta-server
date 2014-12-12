__author__ = 'vliu'

import os,sys,random
import utils
from utils.protocol_pb2 import *
import models.content
from models.player import Player

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class World:
    world=None
    creatures=None

    playerInfo=None
    zones={}
    waves={}
    creatureTypes={}
    mockup=False

    #################### protocol
    @classmethod
    def getWorld(cls):
        if cls.mockup:
            if not cls.world:
                cls.world=utils.protocol_pb2.World()
                cls.world.slug="happyworld"
                for _,z in cls.getZones().items():
                    zone=cls.world.zones.add()
                    zone.CopyFrom(z)
            return cls.world
        else:
            return models.content.GameRule.world_proto

    @classmethod
    def getCreatureTypes(cls):
        if not cls.creatures:
            import  utils.misc
            ct=None
            cls.creatures=RetrieveCreatureTypeRep()
            if cls.mockup:
                ret=cls.creatureTypes
                if len(cls.creatureTypes)<=0:
                    for i in range(9):
                        cls.getCreatureType('Tiger_'+str(i))
                for _,v in cls.creatureTypes.items():
                    c=cls.creatures.creatures.add()
                    c.CopyFrom(v)
            else:
                ct=models.content.GameRule.creature_types_proto
                cls.creatures.creatures.extend(ct)
        return cls.creatures

    #################### others
    @classmethod
    def getZones(cls):
        #get all zones in world
        if 0==len(cls.zones):
            #mock
            for i in range(4):
                zone=Zone()
                zone.slug="Zone_"+str(100+i)
                zone.description=zone.slug
                cls.zones[zone.slug]=zone
        return cls.zones

    @classmethod
    def getZone(cls,slug):
        #return Zone
        cls.getZones()
        zone=cls.zones[slug]
        if zone:
            areas=zone.areas
            if 0==len(areas):
                #mock
                for i in range(4):
                    area=areas.add()
                    area.slug="Area_"+str(100+i)
                    area.description=area.slug
        return zone

    @classmethod
    def getArea(cls,zoneSlug,areaSlug):
        #return Area
        area=None
        zone=cls.getZone(zoneSlug)
        if zone:
            areas=zone.areas
            for a in areas:
                if a.slug==areaSlug:
                    area=a
                    dungeons=area.dungeons
                    if 0==len(dungeons):
                        #mock 5 dungeons
                        for i in range(5):
                            dungeon=dungeons.add()
                            dungeon.slug="Dungeon_"+str(100+i)
                            dungeon.description=dungeon.slug
                            dungeon.reward.softCurrency=10
                            dungeon.reward.hardCurrency=10
                            dungeon.reward.xp=10
                            waves=dungeon.waves
                            if 0==len(dungeons):
                                #mock 4 waves
                                for j in range(4):
                                    wave=waves.append('wave_'+str(j))
                    break
        return area

    @classmethod
    def getWave(cls,zoneId,areaId,slug):
        if not cls.waves.has_key(slug):
            wave=Wave()
            #wave.slug=slug
            wave.layout='Arenas/Layout/FourCorners'
            wave.environment='Arenas/Environment/Environment1'
            wave.arena='Arenas/ArenaBorders'
            for i in range(4):
                j=random.randint(0,29)
                enemy=wave.enemies.add()
                d=cls.getCreature(j)
                enemy.CopyFrom(d)
            cls.waves[slug]=wave
        return cls.waves[slug]

    @classmethod
    def getCreatureType(cls,slug):
        if not cls.creatureTypes.has_key(slug):
            i=random.randint(0,8999)
            c=CreatureType()
            c.displayID=1000+i
            c.slug=slug
            c.baseHP=400+i/100
            c.baseAttack=5+i/1000
            #random skill
            #j=random.randint(0,2)
            #for jj in range(1,j):
            if True:
                s=c.skills.add()
                s.slug='Hit'
                s.trigger.type=ONENEMYATTACK
                s.trigger.parameters.append(1)
                s.effect.type=SHOOTRANDOM
                s.effect.parameters.append(50)
                s.effect.parameters.append(3)
                s=c.skills.add()
                s.slug='Hit'
                s.trigger.type=ONHITBORDER
                s.trigger.parameters.append(1)
                s.effect.type=SHOOTRANDOM
                s.effect.parameters.append(50)
                s.effect.parameters.append(3)
                s=c.skills.add()
                s.slug='Hit'
                s.trigger.type=ONHITBYFRIEND
                s.trigger.parameters.append(1)
                s.effect.type=SHOOTRANDOM
                s.effect.parameters.append(50)
                s.effect.parameters.append(3)

            cls.creatureTypes[slug]=c
        return cls.creatureTypes[slug]

    @classmethod
    def getCreature(cls,i):
        c=CreatureInstance()
        cts=cls.getCreatureTypes()
        c.id=1000+i
        c.slug='Tiger_'+str(i%9)
        c.xp=100+i
        c.level=1+i
        c.plusAttack=100+i
        return c

    @classmethod
    def GetPlayerInfo(cls,player):
        rep=PlayerInfo()
        if cls.mockup:
            rep.userId=1000+random.randint(0,999)
            rep.name='happyl'+str(rep.userId)
            rep.xp=100
            #creatues mock
            for i in range(30):
                d=cls.getCreature(i)
                c=rep.creaturebox.add()
                c.CopyFrom(d)
            #teams mock
            for i in range(1):
                t=rep.teams.add()
                for j in range(3):
                    cid=1000+random.randint(0,29)
                    t.creaturesIds.append(cid)
        else:
            player.set_info(rep)
        return rep

    @staticmethod
    def test():
        zs=World.getZones()
        for zi in zs:
            z=World.getZone(zi)
            if z:
                print 'zone: ',z.name
                for ai in z.areas:
                    a=World.getArea(zi,ai.id)
                    if a:
                        print '\tarea: ',a.name
                        for d in a.dungeons:
                            print '\t\tdungeon: ',d.name
