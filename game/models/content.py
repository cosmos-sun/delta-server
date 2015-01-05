import random
import simplejson
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
        if not data or name not in data:
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
    GEM_EGG     = 'GEM_EGG'

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
    faerie_element_tier = {}
    materials_element_tier = {}
    player_level = {}
    gacha_list = {}
    evolve_config = {}
    gatcha_machines = {}
    material_conversion = {}
    material_slugs = []

    # ==== mocked start ====
    battle_reward_ratio = 0.1
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
    fuse_mega_factor = 2
    extend_creature_space = 5
    creature_space_consume_gems = 5
    energy_consume_gems = 1
    energy_countdown = 30  # in seconds
    helper_conf = {"favorite_factor": 1,
                   "facebook_friend_factor": 2,
                   "friend_factor": 1,
                   "total_num": 10}
    default_player_settings = {
        "attr": {"level": 1,
                 "xp": 0,
                 "coins": 100,
                 "gems": 10,
                 "energy": 20,
                 "hearts": 0,
                 "progress": 0,
                 "max_creatures": 40,
                 },
        "creatures": ["firemouse_01", "woodmouse_01", "watermouse_01",
                      "lightmouse_01", "darkmouse_01",
                      "firemonkey_01", "woodmonkey_01", "watermonkey_01",
                      "lightmonkey_01", "darkmonkey_01",
                      "fireaynt_01", "woodaynt_01", "wateraynt_01",
                      "lightaynt_01", "darkaynt_01"]
    }
    # ==== mocked end ====

    @classmethod
    def get_content(cls):
        try:
            cls.content = Content(version_id=OID).load()

            # load global configs from db
            if cls.content.configs:
                cls.configs = simplejson.loads(cls.content.configs)
                cls.configs_proto = proto.GlobalConfigs()
                assign_value(cls.configs_proto, cls.configs)

                # player level info
                level_info = cls.configs.get("playerLevel")
                if level_info:
                    cls.player_level = dict(zip(range(1, len(level_info) + 1),
                                            level_info))
                # evolution
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

                # materials
                for material in cls.configs.get("craftingMaterial", []):
                    slug = material.get("slug")
                    cls.material_slugs.append(slug)

                    conversion = {}
                    for _info in material.get("conversion", []):
                        conversion[_info.get("slug")] = _info.get("count")
                    if conversion:
                        cls.material_conversion[slug] = conversion

            # load creature from db
            if cls.content.creature_types:
                for t in cls.content.creature_types:
                    d = proto.CreatureType()
                    assign_value(d, simplejson.loads(t))
                    #TODO: only for sampleworld
                    if d.displayID < 500:
                        continue
                    #==========================
                    cls.creature_types_proto.append(d)
                # set up creature types dict
                for c in cls.creature_types_proto:
                    cls.creature_types[c.slug] = c
                    slugs = cls.creature_stars.get(c.starRating, [])
                    slugs.append(c.slug)
                    cls.creature_stars[c.starRating] = slugs

            # load world from db
            if cls.content.world:
                cls.world_proto = proto.World()
                cls.world = simplejson.loads(cls.content.world)
                # build world dict
                for z in cls.world.get('zones'):
                    for a in z.get('areas'):
                        for d in a.get('dungeons'):
                            cls.dungeons[d['slug']] = d
                            for w in d['waves']:
                                for e in w['enemies']:
                                    e['element'] = proto.Element.Name(cls.creature_types[e['slug']].element)
                                if w.get('boss') and w.get('boss').get('slug'):
                                    w['boss']['element'] = proto.Element.Name(cls.creature_types[w['boss']['slug']].element)
                            for e in ('eggs_enemy', 'eggs_boss', 'eggs_map'):
                                d['reward'][e] = cls.build_egg_from_content(e, d['reward'][e])
                            d['reward']['eggs_clearance'] = cls.build_eggs_clearance(d['reward']['eggs_clearance'])
                            d['reward']['eggs'] = d['reward']['eggs_map']
                assign_value(cls.world_proto, cls.world)
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
                cls.faerie_element_tier[i['element'] + str(i['tier'])] = i
            # build material dict
            for i in cls.configs.get('craftingMaterial'):
                cls.materials_element_tier[i['element'] + str(i['tier'])] = i['slug']
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
    def build_eggs_clearance(cls, data):
        if not data: return data
        ret = {'loots': [], 'rates':[], 'total':0}
        for d in data:
            loot = d.split('-')
            rate = int(loot[-1])
            ret['total'] += rate
            ret['rates'].append(ret['total'])
            loot[-1] = '100'
            ret['loots'].append('-'.join(loot))
        ret['loots'] = cls.build_egg_from_content('', ret['loots'])
        return ret

    @classmethod
    def build_egg_from_content(cls, e, data):
        if not data: return data
        eggs_map = (e == 'eggs_map')
        rets = []
        for d in data:
            ret = {}
            d = d.split('-')
            t = d[0]
            if t.lower() == cls.FAERIE_EGG.replace('_', '').lower():
                ret['type'] = cls.FAERIE_EGG
                if eggs_map:
                    ret['creature'] = {'slug': d[1]}
                else:
                    ret['tier'] = str(d[1])
                    ret['rate'] = float(d[2])/100
            elif t.lower() == cls.SELF_EGG.replace('_', '').lower():
                ret['type'] = cls.SELF_EGG
                if eggs_map:
                    ret['creature'] = {'slug': d[1]}
                else:
                    ret['rate'] = float(d[1])/100
            elif t.lower() == cls.MATERIAL_EGG.replace('_', '').lower():
                ret['type'] = cls.MATERIAL_EGG
                if eggs_map:
                    ret['material'] = d[1]
                else:
                    sub = d[1].split('_')
                    ret['element'] = sub[0]
                    ret['tier'] = str(sub[1])
                    ret['rate'] = float(d[2])/100
            elif t.lower() == cls.COIN_EGG.replace('_', '').lower():
                ret['type'] = cls.COIN_EGG
                ret['coins'] = int(d[1])
                ret['rate'] = eggs_map or float(d[2])/100
            elif t.lower() == cls.GEM_EGG.replace('_', '').lower():
                ret['type'] = cls.GEM_EGG
                ret['gems'] = int(d[1])
                ret['rate'] = eggs_map or float(d[2])/100
            rets.append(ret)
        return rets

    # @classmethod
    # def build_gacha_list(cls, data):
    #     slugs = []
    #     if data['type'] == 'STARS':
    #         l = []
    #         for star in data['stars']:
    #             l.extend(cls.creature_stars[star])
    #             slugs.extend(l * data['ratio'])
    #     elif data['type'] == 'SLUG':
    #         slugs.extend(data['slugs'] * data['ratio'])
    #     elif data['type'] == 'SLUG_ELEMENT':
    #         pass
    #     elif data['type'] == 'FAERIE':
    #         l = []
    #         for i in cls.configs['faeries']:
    #             if i['tier'] == data['tier'] and i['element'] in data['elements']:
    #                 l.append(i['slug'])
    #         slugs.extend(l * data['ratio'])
    #     return slugs

    @classmethod
    def find_fist_stage(cls, slug, d):
        if slug in d:
            return cls.find_fist_stage(d[slug], d)
        return slug

    @classmethod
    def true_from_ratio(cls, ratio):
        # only support the ratio is percentage
        return random.randint(1, 100) <= ratio * 100

    @classmethod
    def number_from_range(cls, start, end):
        return random.randint(start, end)

    @classmethod
    def random_from_number(cls, number):
        if number < 1: return 0
        return random.randint(1, number)

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
        return cls.true_from_ratio(float(luck)/100)

    @classmethod
    def battle_drop_egg(cls, droppers, configs, dungeon_reward=False):
        if not dungeon_reward:
            if not cls.true_from_ratio(configs['rate']): return None
            dropper = cls.random_get_from_list(droppers)
        if configs['type'] == cls.SELF_EGG:
            if dungeon_reward:
                slug = configs['creature']['slug']
            else:
                slug = cls.creature_first_stage[dropper['slug']]
            return {'type': cls.SELF_EGG, 'creature':
                {'level': 1, 'slug': slug, 'xp': 0}
            }
        elif configs['type'] == cls.FAERIE_EGG:
            if dungeon_reward:
                f = cls.faerie_types.get(configs['creature']['slug'])
            else:
                f = cls.faerie_element_tier.get(dropper['element'] + configs['tier'])
            faerie = {'type': cls.FAERIE_EGG,
                               'creature': {'level': 1, 'slug': f['slug']}}
            faerie['creature'].update(f['stats'])
            return faerie
        elif configs['type'] == cls.MATERIAL_EGG:
            if dungeon_reward:
                material = configs['material']
            else:
                element = 'NONE' if configs['element'] == 'None' else dropper['element']
                material = cls.materials_element_tier.get(element + configs['tier'])
            return {'type': cls.MATERIAL_EGG, 'material': material}
        elif configs['type'] == cls.COIN_EGG:
            return {'type': cls.COIN_EGG, 'coins': configs['coins']}
        elif configs['type'] == cls.GEM_EGG:
            return {'type': cls.GEM_EGG, 'gems': configs['gems']}
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
