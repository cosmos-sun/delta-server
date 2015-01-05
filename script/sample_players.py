import random
from models.content import GameRule
from models.player import Player
from utils.misc import update_latest_login_players
from utils.settings import FB_SAMPLE_ID


starRating = 2
# use agc_id to identify players, so agc_id must be different
players = [{"name": "Yan Shanshan", "agc_id": "sample_1",
            "facebook_id": FB_SAMPLE_ID},
           {"name": "Philip Beck", "agc_id": "sample_2",
            "facebook_id": FB_SAMPLE_ID},
           {"name": "Ben Holmes", "agc_id": "sample_3",
            "facebook_id": FB_SAMPLE_ID},
           {"name": "Cindy Chen", "agc_id": "sample_4",
            "facebook_id": FB_SAMPLE_ID},
           {"name": "Barack Obama", "agc_id": "sample_5"},
           {"name": "Fan Bingbing", "agc_id": "sample_6"},
           {"name": "Kate Upton", "agc_id": "sample_7"},
           {"name": "Steve Jobs", "agc_id": "sample_8"},
           ]
creatures = None


def gen_creatures():
    return [{c.slug: {"level": c.maxLevel}}
            for c in GameRule.creature_types.itervalues()
            if c.starRating == starRating]


def random_creatures():
    global creatures
    if not creatures:
        creatures = gen_creatures()
    c = random.choice(creatures)
    creatures.remove(c)
    return c


def init_player(attr):
    p = Player.load_by_attribute("agc_id", attr.get("agc_id"))
    p = p and p[0]
    if not p:
        # create players if player not exist
        params = {"default_creatures": random_creatures(),
                  "is_new": True}
        params.update(attr)
        p = Player(**params)
        p.store()
    update_latest_login_players(p.id)


def create_sample_players():
    for p_info in players:
        init_player(p_info)
