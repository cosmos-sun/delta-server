import simplejson
import zmq
from zmq import ZMQError
from pykka.gevent import GeventActor
from utils import log
from utils import settings
from utils import stats_pb2
from utils.misc import assign_value


APPLICATION = 'deltaa'
VERSION = 1

# keep use same name in stats_pb2
DeltaSignIn              = 'DeltaSignIn'
DeltaBattleBegin         = 'DeltaBattleBegin'
DeltaBattleEnd           = 'DeltaBattleEnd'
DeltaEditTeam            = 'DeltaEditTeam'
DeltaFuse                = 'DeltaFuse'
DeltaEvolve              = 'DeltaEvolve'
DeltaSellCreature        = 'DeltaSellCreature'
DeltaGacha               = 'DeltaGacha'
DeltaAddEnergy           = 'DeltaAddEnergy'
DeltaConvertMaterial     = 'DeltaConvertMaterial'
DeltaBuyCreatureSpace    = 'DeltaBuyCreatureSpace'
DeltaRevenueIAP          = 'DeltaRevenueIAP'
DeltaRevenueIAB          = 'DeltaRevenueIAB'

def get_event_type(name):
    return getattr(stats_pb2.Event, name)


class SenderHappyLatte(object):
    """
    The sender to send event to statsServer
    """

    def __init__(self, host=settings.STATS_ZMQ_HOST,
                  port=settings.STATS_ZMQ_PORT):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect("tcp://%s:%d" % (host, port))

    def send(self, data):
        self.socket.send(data)

    def stop(self):
        self.socket.close()
        self.context.term()


class StatsActor(GeventActor):
    _sender = None

    def __init__(self):
        super(StatsActor, self).__init__()

    def on_receive(self, msg):
        # TODO - validate data & send event
        self.do_send(msg)
        #log.info(simplejson.dumps(msg))

    @property
    def sender(self):
        if self._sender is None:
            self._sender = SenderHappyLatte()
        return self._sender

    def do_send(self, data):
        try:
            for k,v in data.items(): print k, v
            print '======='
            e = stats_pb2.Event()
            e.FormatVersion = VERSION
            e.Application = APPLICATION
            e.Timestamp = data['timestamp']
            e.EventType = get_event_type(data['event_name'])
            e.EventName = data['event_name']
            s = e.Extensions[getattr(getattr(stats_pb2, data['event_name']), 'event')]
            assign_value(s, data['data'], stats_pb2)
            self.sender.send(e.SerializeToString())
            print e
        except ZMQError, e:
            log.error("Got error while send data(%s) to stats server: %s" %
                      (str(data), e), exc_info=True)

    def _stop_sender(self):
        #TODO: it will not stop, until the zmq's queue is empty
        if self._sender:
            self._sender.stop()
            self._sender = None

    def on_stop(self):
        super(StatsActor, self).on_stop()
        self._stop_sender()

    def on_failure(self, exception_type, exception_value, traceback):
        super(StatsActor, self).on_failure(exception_type, exception_value,
                                           traceback)
        self._stop_sender()
