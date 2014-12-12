#!/usr/bin/python

from types import FunctionType
from pykka import ActorRegistry
from pykka.gevent import GeventActor

from utils.misc import generate_message
from actor_settings import *

from utils import log


class BaseMessage():
    def __init__(self, t, msg):
        self.type = t
        self.msg = msg


#class BaseActor(pykka.ThreadingActor):
class BaseActor(GeventActor):
    def on_receive(self, msg):
        try:
            return getattr(self, msg['func'])(msg['msg'])
        except Exception, e:
            log.error('Error get func by name: %s', e, exc_info=True)
            # TODO fix return
            return None

    def resp(self, msg):
        #log.info('event send %s' % msg)
        return generate_message(msg)


msg_map = {}
class ActorMeta(type):
    base_func = dir(BaseActor)

    def __new__(cls, name, basses, attrs):
        global msg_map
        instance = type.__new__(cls, name, basses, attrs)
        for a_name, a_v in attrs.iteritems():
            if a_name.startswith("_"):
                # skip internal func
                continue
            if a_name in cls.base_func:
                # skip overwrite func
                continue
            if isinstance(a_v, FunctionType):
                msg_map[a_name] = instance
        return instance


class ParentActor(BaseActor):
    def __init__(self, urn=None):
        super(ParentActor, self).__init__()
        if urn:
            self.actor_ref.actor_urn = urn

    def on_start(self):
        self.actor_ref.actor_urn = self.actor_urn
        ActorRegistry.unregister(self.actor_ref)
        ActorRegistry.register(self.actor_ref)


class ChildActor(BaseActor):
    __metaclass__ = ActorMeta
    def __init__(self, parent):
        super(ChildActor, self).__init__()
        self.parent = parent

    def on_failure(self, exception_type, exception_value, traceback):
        log.error('on failure')
        self.parent.actor_ref.tell({'type': TYPE_ERROR, 'actor': self, 'exception': exception_value, 'traceback': traceback})


