import random
from base_actor import ChildActor
from models.friend import Friend
from models.player import Player
from utils.misc import get_latest_login_players
from utils.protocol_pb2 import FriendAction
from utils.protocol_pb2 import GetHelperRep
from utils.protocol_pb2 import GetHelperResultCode
from utils.protocol_pb2 import ModifyFriendRep
from utils.protocol_pb2 import ModifyFriendResultCode
from utils.protocol_pb2 import Helper
from utils import log


class Social(ChildActor):

    def GetFriendsInfo(self, msg):
        friend = Friend(self.parent.pid)
        resp = friend.get_friends_info()
        return self.resp(resp)

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

    def GetHelper(self, msg):
        # TODO - Design & move factor & helper num to config
        FAVORITE_FACTOR = 4
        FRIEND_FACTOR = 2
        HELPER_NUM = 6
        player_id = self.parent.pid
        friend = Friend(player_id=player_id)
        friends = set(friend.get_friend_list())
        favorites = set(friend.get_favorite_list())
        active_players = set(get_latest_login_players())
        normal_p = active_players - friends - set([player_id])
        normal_f = friends - favorites
        # TODO - Design: filter normal_p
        players = (list(normal_p) + list(normal_f) * FRIEND_FACTOR +
                   list(favorites) * FAVORITE_FACTOR)
        helper_ids = set(range(HELPER_NUM))  # TODO - use: helper_ids = set()
        while len(helper_ids) < HELPER_NUM:
            _ids = random.sample(players, HELPER_NUM - len(helper_ids))
            helper_ids.update(_ids)
        rep = GetHelperRep()
        helpers = []
        for pid in helper_ids:
            h = Helper()
            pid = player_id  # TODO - mockup here, use the real player id
            player = Player(id=pid).load()
            player.set_info(h.player_info, simple_mode=True)
            h.creature.CopyFrom(player.get_help_creature().to_proto_class())
            helpers.append(h)
        rep.helpers.extend(helpers)
        rep.result_code = GetHelperResultCode.Value("GET_HELPER_SUCCESS")
        return self.resp(rep)