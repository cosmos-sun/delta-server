#!/usr/bin/python

import traceback
from pykka import ActorRegistry

from actor_settings import TYPE_ERROR
from base_actor import ParentActor
from account import LinkAccount
from game import Game
from social import Social
from store import ProductsListActor
from base_actor import msg_map
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
        handler = msg_map.get(msg['func'])
        if msg.get("type") == TYPE_ERROR:
            # TODO - handle error.
            log.error(msg['actor'])
            log.error(msg['exception'])
            log.error(traceback.print_tb(msg['traceback']))
        elif handler:
            return self.call(handler, msg)
        else:
            return None

    def call(self, cls, msg):
        try:
            c = cls.start(self)
            return c.ask(msg)
        except Exception, e:
            log.error(e)
            return None