import simplejson
import zmq
from zmq import ZMQError
from pykka.gevent import GeventActor
from utils import log
from utils import settings


class Sender(object):
    """
    The sender to send event to statsServer
    """

    def __index__(self, host=settings.STATS_ZMQ_HOST,
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

    def on_receive(self, msg):
        # TODO - validate data & send event
        log.info(simplejson.dumps(msg))

    @property
    def sender(self):
        if self._sender is None:
            self._sender = Sender()
        return self._sender

    def do_send(self, data):
        try:
            self.sender.send(data)
        except ZMQError, e:
            log.error("Got error while send data(%s) to stats server: %s" %
                      (str(data), e), exc_info=True)

    def _stop_sender(self):
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
