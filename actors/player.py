#!/usr/bin/python

from pykka import ActorRegistry

from base_actor import INVALID_SESSION_PID
from base_actor import ParentActor
from account import LinkAccount
from game import Game
from social import Social
from store import ProductsListActor
from base_actor import msg_map
from models.player import Player as PlayerModel
from models.player import Session

from utils import log


def get_player(session_id):
    session = Session(id=session_id).load()
    if session and session.exist():
        session.refresh_session()
        pid = session.player_id
    else:
        pid = INVALID_SESSION_PID

    player = ActorRegistry.get_by_urn(pid)
    if player is None:
        player = Player.start(pid, session_id)
    return player


class Player(ParentActor):
    def __init__(self, pid=None, session_id=None):
        super(Player, self).__init__(pid)
        self.pid = pid
        self.session_id = session_id
        self.game = None
        self._player = None

    def on_receive(self, msg):
        handler = msg_map.get(msg['func'])
        if handler:
            return self.call(handler, msg)
        else:
            return None

    def call(self, cls, msg):
        try:
            c = cls.start(self)
            return c.ask(msg)
        except Exception, e:
            log.error(e, exc_info=True)
            return None

    @property
    def player(self):
        if self._player is None:
            player = PlayerModel(id=self.pid)
            self._player = player
        self._player.load()
        return self._player