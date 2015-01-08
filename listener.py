#!/usr/bin/python2.7 -u
# run without stdout buffering
#from __future__ import print_function

import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))


from gevent.pywsgi import WSGIServer
from bottle import Bottle, request, static_file

from actors.player import get_player
from actors.account import get_account
from content import content
from script.sample_players import create_sample_players
from utils import log
from utils import settings
from utils.misc import parse_message


app = Bottle()



def build_request_message(request):
    msg = {'func': request.forms.get('name'),
           'msg': {
               'data': parse_message(request.forms.get('name'), request.forms.get('body')),
               'request': request}
    }
    return msg

def build_message(request):
    msg = {'func': request.forms.get('name'),
           'msg': parse_message(request.forms.get('name'),
                                request.forms.get('body'))}
    return msg

@app.route('/test/')
def _test():
    return 'OK'

@app.route('/account/', method='POST')
def _account():
    msg = build_request_message(request)
    account = get_account()
    resp = account.ask(msg)
    return resp

@app.route('/player/<session_id>/', method='POST')
def _player(session_id):
    player = get_player(session_id)
    if not player:
        return "You need sign in to continue."
    msg = build_message(request)
    return player.ask(msg)

#asset bundle file server:file name template<filename.unity3d>
@app.route('/asset/<pid>/:filename#.*.unity3d#/')
def _sendAssetBundle(pid, filename):
    #some path map
    log.debug('sending asset: ', settings.ASSET_BUNDLE_ROOT, filename)
    return static_file(filename, root=settings.ASSET_BUNDLE_ROOT)

def run_server():
    host = settings.LISTEN_HOST
    port = settings.LISTEN_PORT
    #log.info('version=%s', settings.GAME_VERSION)
    try:
        log.info('serving on %s:%s...', host, port)
        WSGIServer((host, port), app).serve_forever()
    except Exception, e:
        log.error('Server', exc_info=e)

def prepare():
    log.info('prepare content')
    try:
        content.main(action='extract')
        create_sample_players()
    except Exception, e:
        log.warning('can not extract content: %s', e)

if __name__ == '__main__':
    # ALTERNATIVES: use nodemon (nodejs app) or Bottle's auto-reload
    prepare()
    import server_reloader
    def hook(): log.warning("reloading code")
    server_reloader.main(run_server, before_reload=hook)
