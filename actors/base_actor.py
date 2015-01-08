#!/usr/bin/python
import time

from types import FunctionType
from pykka import ActorRegistry
from pykka.gevent import GeventActor
from stats import StatsActor, get_event_type

from utils.misc import generate_message

from utils import log


msg_map = {}
INVALID_SESSION_PID = -1


#class BaseActor(pykka.ThreadingActor):
class BaseActor(GeventActor):
    def on_receive(self, msg):
        try:
            return getattr(self, msg['func'])(msg['msg'])
        except Exception, e:
            log.error('Get error: %s', e, exc_info=True)
            # TODO fix return
            return None

    def resp(self, msg):
        return generate_message(msg)

    def send_event(self, event_name, data, player=None, client=None):
        if player:
            data['player'].update(player.get_stats_data())
        if client:
            c = data.get('client', {})
            c['device_type'] = client.device_type
            c['conn_type'] = client.conn_type
            c['client_timestamp'] = client.client_timestamp
            c['client_version'] = client.client_version
            c['device_os'] = client.device_os
            c['device_os_version'] = client.device_os_version
            c['openudid'] = client.openudid
            c['odin'] = client.odin
            c['mac_address'] = client.mac_address
            c['ios_ifa'] = client.ios_ifa
            c['android_id'] = client.android_id
            c['imei'] = client.imei
            c['android_ifa'] = client.android_ifa
            data['client'] = c
        msg = {"event_name": event_name,
               "timestamp": time.time(),
               "data": data}
        actor = ActorRegistry.get_by_class(StatsActor)
        actor = actor and actor[0] or StatsActor.start()
        actor.tell(msg)

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


class MessageHandlerWrapper(object):
    resp_msg = None
    invalid_session_code = None

    def __init__(self, resp_msg, invalid_session_code):
        self.resp_msg = resp_msg
        self.invalid_session_code = invalid_session_code

    def __call__(self, method):
        def handler_wrapper(instance, *args, **kwargs):
            if instance.parent.pid == INVALID_SESSION_PID:
                resp = self.resp_msg()
                resp.result_code = self.invalid_session_code
                return instance.resp(resp)
            else:
                return method(instance, *args, **kwargs)
        return handler_wrapper
