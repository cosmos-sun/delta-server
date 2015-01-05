import random
from base_actor import ChildActor
from base_actor import MessageHandlerWrapper
from models.content import GameRule
from models.friend import Friend
from models.player import Player
from utils.misc import get_latest_login_players
from utils.protocol_pb2 import FriendAction
from utils.protocol_pb2 import GetFriendsInfoRep
from utils.protocol_pb2 import GetFriendsInfoResultCode
from utils.protocol_pb2 import GetHelperRep
from utils.protocol_pb2 import GetHelperResultCode
from utils.protocol_pb2 import ModifyFriendRep
from utils.protocol_pb2 import ModifyFriendResultCode
from utils.protocol_pb2 import Helper
from utils import log


class Social(ChildActor):

    @MessageHandlerWrapper(GetFriendsInfoRep, GetFriendsInfoResultCode.Value(
        "GET_FRIEND_INFO_INVALID_SESSION"))
    def GetFriendsInfo(self, msg):
        friend = Friend(self.parent.pid)
        resp = friend.get_friends_info()
        return self.resp(resp)

    @MessageHandlerWrapper(ModifyFriendRep, ModifyFriendResultCode.Value(
        "MODIFY_FRIEND_INVALID_SESSION"))
    def ModifyFriend(self, msg):
        resp = ModifyFriendRep()
        resp.action = msg.action
        if msg.player_id == self.parent.pid:
            resp.result_code = ModifyFriendResultCode.Value(
                "FRIEND_ON_SELF")
            return self.resp(resp)
        friend = Friend(player_id=self.parent.pid)
        try:
            action = FriendAction.Name(msg.action).lower()
        except ValueError, e:
            log.info("Modify friend get unsupported action - %s" % e)
            resp.result_code = ModifyFriendResultCode.Value(
                "UNSUPPORTED_ACTION")
            return self.resp(resp)
        func = getattr(friend, action)
        if not func:
            log.debug("Modify friend not implement action: %s" % action)
            resp.result_code = ModifyFriendResultCode.Value(
                "UNSUPPORTED_ACTION")
        elif not Player(id=msg.player_id).exist():
            resp.result_code = ModifyFriendResultCode.Value(
                "FRIEND_NOT_EXIST")
        else:
            resp.result_code = func(msg.player_id)
        return self.resp(resp)

    @MessageHandlerWrapper(GetHelperRep, GetHelperResultCode.Value(
        "GET_HELPER_INVALID_SESSION"))
    def GetHelper(self, msg):
        helper_conf = GameRule.helper_conf
        fb_friend_factor = helper_conf.get("facebook_friend_factor")
        favorite_factor = helper_conf.get("favorite_factor")
        friend_factor = helper_conf.get("friend_factor")
        helper_num = helper_conf.get("total_num")
        player_id = self.parent.pid
        friend = Friend(player_id=player_id)
        friends = set(friend.get_friend_list())
        favorites = set(friend.get_favorite_list())
        fb_friends = set(friend.get_facebook_list())
        active_players = set(get_latest_login_players())
        normal_p = active_players - friends - fb_friends - set([player_id])
        favorites = favorites - fb_friends
        normal_f = friends - favorites - fb_friends
        # TODO - Design: filter normal_p
        players = (list(fb_friends) * fb_friend_factor +
                   list(favorites) * favorite_factor +
                   list(normal_f) * friend_factor +
                   list(normal_p))
        _players = set(players)
        if len(_players) <= helper_num:
            helper_ids = _players
        else:
            helper_ids = set()
            while len(helper_ids) < helper_num:
                _ids = random.sample(players, helper_num - len(helper_ids))
                helper_ids.update(_ids)
        rep = GetHelperRep()
        helpers = []
        for pid in helper_ids:
            h = Helper()
            player = Player(id=pid).load()
            player.set_info(h.player_info, simple_mode=True)
            h.creature.CopyFrom(player.get_help_creature().to_proto_class())
            helpers.append(h)
        rep.helpers.extend(helpers)
        rep.result_code = GetHelperResultCode.Value("GET_HELPER_SUCCESS")
        return self.resp(rep)