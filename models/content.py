import os, sys, random, base64, json

from dal.base import Base
from dal.base import IntAttr, ListAttr, PickleAttr, TextAttr
from utils import log
from utils import protocol_pb2 as proto
from utils.protocol_pb2 import Element

OID = 0


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
    configs = TextAttr()
    creature_types = ListAttr(TextAttr())
    _oid_key = "version_id"


class GameRule(object):
    FAERIE_EGG  = 'FAERIE_EGG'
    SELF_EGG     = 'SELF_EGG'
    MATERIAL_EGG = 'MATERIAL_EGG'
    COIN_EGG     = 'COIN_EGG'

    configs = None
    configs_proto = None
    dungeons = {}
    world = {}
    world_proto = None
    creature_types_proto = []
    creature_types = {}
    creature_first_stage = {}
    creature_stars = {}
    creature_series = {}
    faerie_types = {}
    player_level = {}
    gacha_list = {}
    evolve_config = {}
    gatcha_machines = {}
    # mocked
    battle_enemy_egg_ratio = 0.3
    battle_boss_egg_ratio = 1
    battle_reward_ratio = 0.1
    battle_egg_type_ratio = {
        FAERIE_EGG: 1,
        SELF_EGG: 1,
        MATERIAL_EGG: 1,
        COIN_EGG: 1,
    }
    material_none_drop_ratio = (
        (10,1),
        (30,2),
        (50,3),
        (70,4),
    )
    material_element_drop_ratio = (
        (35,1),
        (70,2),
    )
    faerie_drop_ratio = (
        (30,1),
        (60,2),
        (90,3),
    )
    gacha_trees = {
        'tree1': [
            {'type': 'STARS', 'stars':  [1,2,3], 'ratio': 2},
            {'type': 'SLUG', 'slugs': ['mouse_01'], 'ratio': 3},
        ],
        'tree2': [
            {'type': 'SLUG_ELEMENT', 'slugs': ['mouse_01'], 'elements': ['water'], 'ratio': 3},
            {'type': 'FAERIE', 'elements': ['WATER'], 'tier': 1, 'ratio': 3},
        ],
    }

    @classmethod
    def get_content(cls):
        try:
            cls.content = Content(version_id=OID).load()

            # load global configs from db
            if cls.content.configs:
                cls.configs = json.loads(cls.content.configs)
                cls.configs_proto = proto.GlobalConfigs()
                assign_value(cls.configs_proto, cls.configs)
                level_info = cls.configs.get("playerLevel")
                if level_info:
                    cls.player_level = dict(zip(range(1, len(level_info) + 1),
                                            level_info))

                tier_map = {1: "s", 2: "l"}
                for evolve_info in cls.configs.get("evolutionDefinition"):
                    _conf = {}
                    star_rank = evolve_info.get("fromStarRank")
                    cls.evolve_config[star_rank] = _conf
                    _conf["softCurrency"] = evolve_info.get("softCurrency")

                    non_element = {}
                    for m_info in evolve_info.get("cost"):
                        non_element[m_info.get("slug")] = m_info.get("count")
                    _conf["non_element"] = non_element
                    if not evolve_info.get("elementalCost"):
                        continue

                    for e_name, e_val in Element.items():
                        if "NONE" == e_name:
                            continue
                        element = {}
                        e_name = e_name.lower()
                        for m_info in evolve_info.get("elementalCost"):
                            slug = "stone_%s_%s" %\
                                   (e_name, tier_map.get(m_info.get("tier")))
                            element[slug] = m_info.get("count")
                        _conf[e_val] = element
            # load world from db
            if cls.content.world:
                cls.world_proto = proto.World()
                assign_value(cls.world_proto, json.loads(cls.content.world))
                # set up world dict
                for zone in cls.world_proto.zones:
                    for area in zone.areas:
                        for dungeon in area.dungeons:
                            cls.dungeons[dungeon.slug] = dungeon
                for zone in cls.world_proto.zones:
                    cls.world[zone.slug] = {
                        'requirement': zone.requirement,
                    }
                    for area in zone.areas:
                        cls.world[zone.slug][area.slug] = {
                            'requirement': area.requirement,
                        }
                        for dungeon in area.dungeons:
                            cls.world[zone.slug][area.slug][dungeon.slug] = dungeon
            # load creature from db
            if cls.content.creature_types:
                for t in cls.content.creature_types:
                    d = proto.CreatureType()
                    assign_value(d, json.loads(t))
                    #TODO: only for sampleworld
                    if d.displayID < 500:
                        continue
                    cls.creature_types_proto.append(d)
                # set up creature types dict
                for c in cls.creature_types_proto:
                    cls.creature_types[c.slug] = c
                    slugs = cls.creature_stars.get(c.starRating, [])
                    slugs.append(c.slug)
                    cls.creature_stars[c.starRating] = slugs
                #for i in cls.creature_types_proto: print i.displayID, i.slug
                # get first stage
                tmp_dict = {}
                for k, v in cls.creature_types.iteritems():
                    if k not in tmp_dict:
                        tmp_dict[v.evolutionSlug.lower()] = k.lower()
                for slug, prev in tmp_dict.iteritems():
                    first = cls.find_fist_stage(slug, tmp_dict)
                    if slug == '': continue
                    cls.creature_first_stage[slug] = first

                for i in cls.creature_first_stage.values():
                    cls.creature_first_stage[i] = i

                # creature series
                for slug, creature in cls.creature_types.iteritems():
                    slug = slug.lower()
                    evolve_slug = creature.evolutionSlug.lower()
                    if not evolve_slug:
                        continue
                    orig_series = cls.creature_series.get(slug)
                    evolve_series = cls.creature_series.get(evolve_slug)
                    if not orig_series and not evolve_series:
                        series = [slug, evolve_slug]
                        cls.creature_series[slug] = series
                        cls.creature_series[evolve_slug] = series
                    elif orig_series and not evolve_series:
                        orig_series.append(evolve_slug)
                        cls.creature_series[evolve_slug] = orig_series
                    elif evolve_series and not orig_series:
                        evolve_series.append(slug)
                        cls.creature_series[slug] = evolve_series
                    else:
                        orig_series.extend(evolve_series)
                        for _slug in evolve_series:
                            cls.creature_series[_slug] = orig_series
            # build faeries dict
            for i in cls.configs.get('faeries'):
                cls.faerie_types[i['slug']] = i

            #build gacha machines
            for i in cls.configs.get('gatchaMachine'):
                cls.gacha_list[i['slug']] = []
                for drop in i['drops']:
                    cls.gacha_list[i['slug']].extend([drop['creatureSlug']] * drop['weight'])
            ## build gacha trees slug list, mocked now
            #for tree, data in cls.gacha_trees.iteritems():
            #    cls.gacha_list[tree] = []
            #    for d in data:
            #        cls.gacha_list[tree].extend(cls.build_gacha_list(d))
        except Exception, e:
            log.error('can not load content: %s', e, exc_info=True)

    @classmethod
    def build_gacha_list(cls, data):
        slugs = []
        if data['type'] == 'STARS':
            l = []
            for star in data['stars']:
                l.extend(cls.creature_stars[star])
                slugs.extend(l * data['ratio'])
        elif data['type'] == 'SLUG':
            slugs.extend(data['slugs'] * data['ratio'])
        elif data['type'] == 'SLUG_ELEMENT':
            pass
        elif data['type'] == 'FAERIE':
            l = []
            for i in cls.configs['faeries']:
                if i['tier'] == data['tier'] and i['element'] in data['elements']:
                    l.append(i['slug'])
            slugs.extend(l * data['ratio'])
        return slugs

    @classmethod
    def find_fist_stage(cls, slug, d):
        if slug in d:
            return cls.find_fist_stage(d[slug], d)
        return slug

    @classmethod
    def true_from_ratio(cls, ratio):
        # only support the ratio is percentage
        return random.randint(0, 100) <= ratio * 100

    @classmethod
    def number_from_range(cls, start, end):
        return random.randint(start, end)

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
        for k, v in d.iteritems():
            ls.extend((k,) * v)
        return cls.random_get_from_list(ls)

    @classmethod
    def get_creature_id_by_slug(cls, slug):
        return cls.creature_types[slug].id

    @classmethod
    def battle_drop_luck_egg(cls, luck):
        #TODO: need design
        return True

    @classmethod
    def battle_drop_egg(cls, dropper, elements):
        def teir_from_ratio(level, ratio):
            start_tier = ratio[0]
            end_tier = None
            for i in range(len(ratio)):
                if ratio[i][0] >= level:
                    end_tier = ratio[i]
                    break
                start_tier = ratio[i]
            end_tier = end_tier or start_tier
            tier = start_tier[1]
            if level >= cls.number_from_range(start_tier[0], end_tier[0]):
                tier = end_tier[1]
            return tier

        if not elements: elements = []
        kind = cls.list_with_ratio(cls.battle_egg_type_ratio)
        if kind == cls.MATERIAL_EGG:
            element = cls.random_get_from_list(list(elements) + ['NONE'])
            if element == 'NONE':
                tier = teir_from_ratio(dropper.level, cls.material_none_drop_ratio)
            else:
                tier = teir_from_ratio(dropper.level, cls.material_element_drop_ratio)
            matreial = None
            #TODO: change this config to be a dict, faster than loop list
            for i in GameRule.configs['craftingMaterial']:
                if i['element'] == element and i['tier'] == tier:
                    matreial = i['slug']
                    break
            return {'type': cls.MATERIAL_EGG, 'material': matreial}
        elif kind == cls.FAERIE_EGG:
            element = cls.random_get_from_list(list(elements))
            tier = teir_from_ratio(dropper.level, cls.faerie_drop_ratio)
            faerie = None
            #TODO: change this config to be a dict, faster than loop list
            for i in cls.configs['faeries']:
                if i['element'] == element and i['tier'] == tier:
                    faerie =  {'type': cls.FAERIE_EGG,
                               'creature': {'level': 1, 'slug': i['slug']}}
                    faerie['creature'].update(i['stats'])
                    break
            return faerie
        elif kind == cls.COIN_EGG:
            #TODO: how much coin should give
            coins = cls.number_with_ratio(dropper.level*500, cls.battle_reward_ratio)
            return {'type': cls.COIN_EGG, 'coins': int(coins)}
        elif kind == cls.SELF_EGG:
            slug = cls.creature_first_stage[dropper.slug]
            return {'type': cls.SELF_EGG, 'creature':
                {'level': 1, 'slug': slug, 'xp': 0}
            }
        return None

    @classmethod
    def gacha(cls, tree_slug):
        slug = cls.random_get_from_list(cls.gacha_list.get(tree_slug))
        if slug in cls.faerie_types:
            faerie = {'type': cls.FAERIE_EGG,
                      'creature': {'level': 1, 'slug': slug}}
            faerie['creature'].update(cls.faerie_types[slug]['stats'])
            return faerie
        else:
            slug = cls.creature_first_stage[slug]
            return {'type': cls.SELF_EGG, 'creature': {'level': 1, 'slug': slug, 'xp': 0}}

GameRule.get_content()
