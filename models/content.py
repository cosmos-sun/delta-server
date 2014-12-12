import os, sys, random, base64, json

from dal.base import Base
from dal.base import IntAttr, ListAttr, PickleAttr, TextAttr
from utils import log
from utils import protocol_pb2 as proto


OID = 0
FAERIE_EGG  = 'FAERIE_EGG'
SELF_EGG     = 'SELF_EGG'
MATERIAL_EGG = 'MATERIAL_EGG'
COIN_EGG     = 'COIN_EGG'


def build_enum_type(name):
    return '_' + name.upper()

def assign_value(inst, data):
    for name, value in inst.DESCRIPTOR.fields_by_name.items():
        if name not in data:
            continue
        attr = getattr(inst, name)
        if hasattr(attr, 'DESCRIPTOR'):
            assign_value(attr, data[name])
        else:
            if type(data[name]) is list:
                l = []
                if hasattr(value.message_type, 'name') and getattr(value.message_type, 'name') is not None:
                    cls = getattr(proto, value.message_type.name)
                    for d in data[name]:
                        sub_inst = cls()
                        assign_value(sub_inst, d)
                        l.append(sub_inst)
                else:
                    for d in data[name]:
                        l.append(d)
                getattr(inst, name).extend(l)
            else:
                if hasattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') and getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') is not None:
                        enum_type = getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type').name
                        enum_inst = getattr(proto, build_enum_type(enum_type))
                        d = enum_inst.values_by_name[data[name]].number
                        setattr(inst, name, d)
                else:
                    setattr(inst, name, data[name])


class Content(Base):
    version_id = IntAttr()
    world = TextAttr()
    creature_types = ListAttr(TextAttr())
    _oid_key = "version_id"


class GameRule(object):

    battle_enemy_egg_ratio = 0.1
    battle_boss_egg_ratio = 0.01
    battle_reward_ratio = 0.1
    battle_egg_type_ratio = {
        FAERIE_EGG: 1,
        SELF_EGG: 1,
        MATERIAL_EGG: 1,
        COIN_EGG: 1,
    }

    world_proto = None
    creature_types_proto = []
    dungeons = {}
    creature_types = {}
    creature_stars = {}
    faerie_types = {
        'warfaerie_01': {
            'slug': 'warfaerie_01',
            'tier': 1,
            'element': 'FIRE',
            'stat_type': 'ATTACK',
            'stat_number': 5,
            }
    }
    gacha_trees = {
        'tree1': [
            {'type': 'STARS', 'stars': [0], 'ratio': 2},
            {'type': 'SLUG', 'slugs': ['mouse_01'], 'ratio': 3},
        ],
        'tree2': [
            {'type': 'SLUG_ELEMENT', 'slugs': ['mouse_01'], 'elements': ['water'], 'ratio': 3},
            {'type': 'FAERIE', 'skill': 'asdf', 'tier': 1, 'ratio': 3},
        ],
    }

    @classmethod
    def get_content(cls):
        try:
            cls.content = Content(version_id=OID).load()

            # load world from db
            if cls.content.world:
                cls.world_proto = proto.World()
                assign_value(cls.world_proto, json.loads(cls.content.world))
                # set up world dict
                for zone in cls.world_proto.zones:
                    for area in zone.areas:
                        for dungeon in area.dungeons:
                            cls.dungeons[dungeon.slug] = dungeon
            # load creature from db
            if cls.content.creature_types:
                for t in cls.content.creature_types:
                    d = proto.CreatureType()
                    assign_value(d, json.loads(t))
                    cls.creature_types_proto.append(d)
                # set up creature types dict
                for c in cls.creature_types_proto:
                    cls.creature_types[c.slug] = c
                    slugs = cls.creature_stars.get(c.starRating, [])
                    slugs.append(c.slug)
                    cls.creature_stars[c.starRating] = slugs
        except Exception, e:
            log.error('can not load content: %s', e, exc_info=True)

    @classmethod
    def true_from_ratio(cls, ratio):
        # only support the ratio is percentage
        return random.randint(0, 100 * (1 - ratio)) == 0

    @classmethod
    def number_with_ratio(cls, number, ratio, integer=False):
        ret = random.uniform(1-ratio, 1+ratio) * number
        return int(ret) if integer else ret

    @classmethod
    def random_get_from_list(cls, l):
        return random.choice(l)

    @classmethod
    def list_with_ratio(cls, d):
        ls = []
        for k, v in d:
            ls.extend((k,) * v)
        return cls.random_get_from_list(ls)

    @classmethod
    def get_creature_id_by_slug(cls, slug):
        return cls.creature_types[slug].id

    @classmethod
    def get_first_stage(cls, slug):
        #TODO: need design
        return slug

    @classmethod
    def create_egg(cls, egg_type, slug, level=None, element=None):
        pass

    @classmethod
    def battle_drop_luck_egg(cls, luck):
        #TODO: need design
        return True
    @classmethod
    def battle_drop_egg(cls, dropper, elements):
        kind = cls.list_with_ratio(cls.battle_egg_type_ratio)
        data = None
        #TODO: rules for egg
        if kind == MATERIAL_EGG:
            pass
        elif kind == SELF_EGG:
            pass
        elif kind == MATERIAL_EGG:
            pass
        elif kind == COIN_EGG:
            data = cls.number_with_ratio(dropper.level*500, cls.battle_reward_ratio)

        return kind, data

    @classmethod
    def battle_wave_egg(cls, dropper, elements, boss=False):
        ratio = cls.battle_boss_egg_ratio \
                if boss else cls.battle_enemy_egg_ratio
        if not cls.true_from_ratio(ratio):
            return None
        return cls.battle_drop_egg(dropper, elements)

    @classmethod
    def battle_xp(cls, creature_level):
        xp = creature_level * 500
        return cls.number_with_ratio(xp, cls.battle_reward_ratio, True)

    @classmethod
    def gacha_egg_list(cls, **data):
        slugs = []
        if data['type'] == 'STARS':
            l = []
            for star in data['stars']:
                print star
                print cls.creature_stars.keys()
                l.extend(cls.creature_stars[star])
                slugs.extend(l * data['ratio'])
        elif data['type'] == 'SLUG':
            slugs.extend(data['slugs'] * data['ratio'])
        elif data['type'] == 'SLUG_ELEMENT':
            pass # {'type': 'SLUG_ELEMENT', 'slugs': ['mouse_01'], 'elements': ['water'], 'ratio': 3},
        elif data['type'] == 'FAERIE':
            pass # {'type': 'FAERIE', 'skill': 'asdf', 'tier': 1, 'ratio': 3},

        return slugs

    @classmethod
    def gacha(cls, tree_slug):
        data_dict = cls.gacha_trees[tree_slug]
        slugs = []
        for data in data_dict:
            slugs.extend(cls.gacha_egg_list(**data))
        slug = cls.random_get_from_list(slugs)
        kind = FAERIE_EGG if slug in cls.faerie_types else SELF_EGG
        return kind, slug

GameRule.get_content()