#!/usr/bin/python
from pykka import ActorRegistry
from base_actor import ParentActor
from base_actor import ChildActor
from utils import log
from utils.protocol_pb2 import LinkAccountRep
from utils.protocol_pb2 import LinkAccountResultCode
from utils.protocol_pb2 import SignInRep
from utils.protocol_pb2 import SignInResultCode
from utils.protocol_pb2 import SignUpRep
from utils.protocol_pb2 import SignUpResultCode
from utils.protocol_pb2 import SignType
from utils.misc import update_latest_login_players
from models.player import DeviceLink
from models.player import Player
from models.player import Session
from configs.world import World


def get_account():
    account = ActorRegistry.get_by_class(Account)
    return account and account[0] or Account.start()


class BaseAuth(object):

    @property
    def player_index(self):
        raise NotImplementedError

    def get_player(self, val):
        data = Player.load_by_attribute(self.player_index, val)
        return data and data[0]

    def get_player_by_device(self, device_id):
        device = DeviceLink(device_id=device_id).load()
        player_id = device.player_id
        if player_id:
            player = Player(id=player_id)
            player.load()
            return player
        return

    def generate_session(self, player_id):
        session = Session(player_id=player_id)
        session.store()
        session.refresh_session()
        return session


class BaseSignUp(BaseAuth):

    def handle_signup(self, msg):
        resp = SignUpRep()
        # duplicate verify.
        if self.get_player(msg.account):
            resp.result_code = SignUpResultCode.Value("DUPLICATE_ACCOUNT_ID")
            return resp
        # TODO - verify with 3rd party?
        player_kwargs = {"name": msg.name,
                         "is_new": True,
                         self.player_index: msg.account}
        self.init_player(player_kwargs)
        resp.result_code = SignUpResultCode.Value("SIGNUP_SUCCESS")
        return resp

    def init_player(self, player_kwargs):
        player = Player(**player_kwargs)
        player.store()
        return player


class BaseSignIn(BaseAuth):

    def handle_signin(self, msg):
        resp = SignInRep()
        player = self.get_player(msg.account)
        # check whether player exist.
        if not player:
            resp.result_code = SignInResultCode.Value("PLAYER_NOT_EXIST")
            return resp
        session = Session.load_by_attribute("player_id", player.id)
        session = session and session[0]
        if session:
            session.delete()
            # TODO - handle duplicate login
        session = self.generate_session(player.id)
        update_latest_login_players(player.id)

        resp.session_id = session.id
        resp.result_code = SignInResultCode.Value("SIGNIN_SUCCESS")
        resp.player_info.CopyFrom(World.GetPlayerInfo(player))
        return resp


class BaseLinkAccount(BaseAuth):
    """
    Link PIP account to player data.
    """

    def handle_link(self, player_id, msg):
        device_player = self.get_player_by_device(msg.device_id)
        if device_player is None:
            return LinkAccountResultCode.Value("LINK_ACC_DEVICE_ID_NOT_EXIST")
        if device_player.id != player_id:
            return LinkAccountResultCode.Value("LINK_ACC_PLAYER_NOT_MATCH")

        player = self.get_player(msg.pip_id)
        if player:
            if player.id != device_player.id:
                return LinkAccountResultCode.Value("LINK_ACC_DIFFERENT_PIP")
            else:
                return LinkAccountResultCode.Value("LINK_ACC_ALREADY_LINKED")
        elif getattr(device_player, self.player_index):
            return LinkAccountResultCode.Value(
                "LINK_ACC_DEVICE_LINKED_TO_OTHER_PIP")
        else:
            # Do link
            setattr(device_player, self.player_index, msg.pip_id)
            device_player.store()
            return LinkAccountResultCode.Value("LINK_ACC_SUCCESS")


class BaseAGC(BaseAuth):

    @property
    def player_index(self):
        return "agc_id"


class AGCSignUp(BaseSignUp, BaseAGC):
    pass


class AGCSignIn(BaseSignIn, BaseAGC):
    pass


class LinkAGC(BaseLinkAccount, BaseAGC):
    pass


class BaseGoogle(BaseAuth):

    @property
    def player_index(self):
        return "gc_id"


class GoogleSignUp(BaseSignUp, BaseGoogle):
    pass


class GoogleSignIn(BaseSignIn, BaseGoogle):
    pass


class LinkGoogle(BaseLinkAccount, BaseGoogle):
    pass


class BaseFacebook(BaseAuth):

    @property
    def player_index(self):
        return "facebook_id"


class FacebookSignUp(BaseSignUp, BaseFacebook):
    pass


class FacebookSignIn(BaseSignIn, BaseFacebook):
    pass


class LinkFacebook(BaseLinkAccount, BaseFacebook):
    pass


class BaseDevice(BaseAuth):

    @property
    def player_index(self):
        return "device_id"


class DeviceSignUp(BaseSignUp, BaseDevice):
    pass


class DeviceSignIn(BaseSignIn, BaseDevice):
    pass


class Account(ParentActor):
    signup_map = {SignType.Value("APPLE"): AGCSignUp(),
                  SignType.Value("GOOGLE"): GoogleSignUp(),
                  SignType.Value("FACEBOOK"): FacebookSignUp(),
                  SignType.Value("DEVICE"): DeviceSignUp(),
                  }
    signin_map = {SignType.Value("APPLE"): AGCSignIn(),
                  SignType.Value("GOOGLE"): GoogleSignIn(),
                  SignType.Value("FACEBOOK"): FacebookSignIn(),
                  SignType.Value("DEVICE"): DeviceSignIn(),
                  }

    def SignUp(self, msg):
        log.info('account signup receive %s' % msg)
        sign_type = msg.type
        if sign_type:
            resp = self.signup_map.get(msg.type).handle_signup(msg)
        else:
            resp = SignUpRep()
            resp.result_code = SignUpResultCode.Value("MISSING_SIGNUP_TYPE")
        return self.resp(resp)

    def SignIn(self, msg):
        log.info('account sign in receive %s' % msg)
        handler = self.signin_map.get(msg.type)
        if handler:
            resp = handler.handle_signin(msg)
        else:
            resp = SignInRep()
            resp.result_code = SignInResultCode.Value("MISSING_SIGN_IN_TYPE")
        return self.resp(resp)


class LinkAccount(ChildActor):
    link_acc_map = {SignType.Value("APPLE"): LinkAGC(),
                    SignType.Value("GOOGLE"): LinkGoogle(),
                    SignType.Value("FACEBOOK"): LinkFacebook(),
                    }

    def LinkAccount(self, msg):
        log.info("link account receive %s" % msg)
        resp = LinkAccountRep()
        link_handler = self.link_acc_map.get(msg.type)
        if link_handler:
            resp.result_code = link_handler.handle_link(self.parent.pid, msg)
        elif msg.type in SignType.values():
            resp.result_code = LinkAccountResultCode.Value(
                "LINK_ACC_DISABLED_SIGN_TYPE")
        else:
            resp.result_code = LinkAccountResultCode.Value(
                "LINK_ACC_MISSING_SIGN_TYPE")
        return self.resp(resp)