import os, sys, base64
#sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))


from dal.base import Base
from dal.base import IntAttr, ListAttr, PickleAttr, TextAttr
from utils import log, protocol_pb2

OID = 0

class Content(Base):
    version_id = IntAttr()
    world = TextAttr()
    creature_types = ListAttr(TextAttr())
    _oid_key = "version_id"

content = None

world = {}
creature_types = {}
creature_stars = {}
world_proto = None
creature_types_proto = []

try:
    content = Content(version_id=OID).load()
    world_proto = protocol_pb2.World()
    world_proto.ParseFromString(base64.b64decode(content.world))
    for t in content.creature_types:
        d = protocol_pb2.CreatureType()
        d.ParseFromString(base64.b64decode(t))
        creature_types_proto.append(d)
    if content:
        for zone in world_proto.zones:
            world[zone.slug] = {
                'requirement': zone.requirement,
            }
            for area in zone.areas:
                world[zone.slug][area.slug] = {
                    'requirement': area.requirement,
                }
                for dungeon in area.dungeons:
                    world[zone.slug][area.slug][dungeon.slug] = dungeon

        for c in creature_types_proto:
            creature_types[c.slug] = c
            slugs = creature_stars.get(c.starRating, [])
            slugs.append(c.slug)
            creature_stars[c.starRating] = slugs
except Exception, e:
    log.error('can not load content: %s', e, exc_info=True)
