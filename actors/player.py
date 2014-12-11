#!/usr/bin/python

import traceback
from pykka import ActorRegistry

from actor_settings import *
from base_actor import ParentActor
from game import Game
from social import Social
from store import ProductsListActor
from models.player import Session

from utils import log


def get_player(session_id):
    session = Session(id=session_id).load()
    if not session:
        return
    session.refresh_session()
    pid = session.player_id
    player = ActorRegistry.get_by_urn(pid)
    if player is None:
        player = Player.start(pid)
    return player


class Player(ParentActor):
    def __init__(self, pid=None):
        super(Player, self).__init__(pid)
        self.pid = pid
        self.game = None

    def on_receive(self, msg):
        if msg['type'] == TYPE_GAME:
            return self.call(Game, msg)
        elif msg['type'] == TYPE_STORE:
            return self.call(ProductsListActor, msg)
        elif msg["type"] == TYPE_SOCIAL:
            return self.call(Social, msg)
        elif msg['type'] == TYPE_ERROR:
            log.error(msg['actor'])
            log.error(msg['exception'])
            log.error(traceback.print_tb(msg['traceback']))
        else:
            return None

    def call(self, cls, msg):
        try:
            c = cls.start(self)
            return c.ask(msg)
        except Exception, e:
            log.error(e)
            return None