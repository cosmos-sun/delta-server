from dal.base import *
from models.player import Player
from utils.exception import UnsupportedFriendAction
from utils.protocol_pb2 import FriendInfo
from utils.protocol_pb2 import GetFriendsInfoRep
from utils.protocol_pb2 import GetFriendsInfoResultCode
from utils.protocol_pb2 import ModifyFriendResultCode


class FriendBase(Base):
    _oid_key = "player_id"
    player_id = LongAttr()
    player_list = ListAttr(LongAttr())
    _loaded = False

    def load(self):
        super(FriendBase, self).load()
        if self._data.get('player_list') is None:
            self._data['player_list'] = []

    def get_list(self):
        if not self._loaded:
            self.load()
            self._loaded = True
        return self.player_list

    def in_list(self, player_id):
        return player_id in self.get_list()

    def add_to_list(self, player_id):
        if player_id not in self.get_list():
            self.player_list.append(player_id)
            self.store()

    def remove_from_list(self, player_id):
        if player_id in self.get_list():
            self.player_list.remove(player_id)
            self.store()

    def generate_proto(self, player_id):
        player = Player(id=player_id).load()
        return player.to_proto_class(simple_mode=True)

    def to_proto_list(self):
        return [self.generate_proto(p_id) for p_id in self.get_list()]


class FriendList(FriendBase):
    _oid_key = "player_id"
    player_id = LongAttr()
    player_list = ListAttr(LongAttr())
    _favorite_list = None

    def get_favorite_list(self):
        if self._favorite_list is None:
            favorite_l = FavoriteList(player_id=self.player_id)
            self._favorite_list = favorite_l.get_list()
        return self._favorite_list

    def generate_proto(self, player_id):
        friend = FriendInfo()
        player = Player(id=player_id).load()
        player.set_info(friend.player_info, simple_mode=True)
        friend.is_favorite = player_id in self.get_favorite_list()
        return friend


class FavoriteList(FriendBase):
    _oid_key = "player_id"
    player_id = LongAttr()
    player_list = ListAttr(LongAttr())

    def to_proto_class(self):
        raise UnsupportedFriendAction("FavoriteList to protocol")


class SendPendingList(FriendBase):
    _oid_key = "player_id"
    player_id = LongAttr()
    player_list = ListAttr(LongAttr())


class ReceivePendingList(FriendBase):
    _oid_key = "player_id"
    player_id = LongAttr()
    player_list = ListAttr(LongAttr())


class Friend(object):
    player_id = None
    friend_list = None
    send_list = None
    receive_list = None
    favorite_list = None
    other_friend_list = None
    other_send_list = None
    other_receive_list = None
    other_favorite_list = None

    def __init__(self, player_id):
        super(Friend, self).__init__()
        self.player_id = player_id
        self.friend_list = FriendList(player_id=player_id)
        self.send_list = SendPendingList(player_id=player_id)
        self.receive_list = ReceivePendingList(player_id=player_id)
        self.favorite_list = FavoriteList(player_id=player_id)

    def init_other_list(self, friend_id):
        self.other_friend_list = FriendList(player_id=friend_id)
        self.other_send_list = SendPendingList(player_id=friend_id)
        self.other_receive_list = ReceivePendingList(player_id=friend_id)
        self.other_favorite_list = FavoriteList(player_id=friend_id)

    def add_friend(self, friend_id):
        self.init_other_list(friend_id)
        # check if player already have this friend
        if self.friend_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("FRIEND_FRIEND")
        if self.receive_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("FRIEND_RECEIVING")
        # add player to friend's receive pending list
        self.other_receive_list.add_to_list(self.player_id)
        # add friend to player's send pending list
        if self.send_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("FRIEND_SENDING")
        else:
            self.send_list.add_to_list(friend_id)
            return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def accept_friend(self, friend_id):
        self.init_other_list(friend_id)
        if not self.receive_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("ACCEPT_NOT_RECEIVING")

        # remove from other's send pending
        self.other_send_list.remove_from_list(self.player_id)
        # add friend to each other's friend list
        self.friend_list.add_to_list(friend_id)
        self.other_friend_list.add_to_list(self.player_id)
        # remove from receive pending
        self.receive_list.remove_from_list(friend_id)
        return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def ignore_friend(self, friend_id):
        self.init_other_list(friend_id)
        # remove from other's send pending list
        self.other_send_list.remove_from_list(self.player_id)
        # remove from player's receive pending list
        if not self.receive_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("IGNORE_NOT_RECEIVING")
        else:
            self.receive_list.remove_from_list(friend_id)
            return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def remove_friend(self, friend_id):
        self.init_other_list(friend_id)
        if not self.friend_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("REMOVE_STRANGER")
        # remove from each other's favorite & friend list
        self.favorite_list.remove_from_list(friend_id)
        self.friend_list.remove_from_list(friend_id)
        self.other_favorite_list.remove_from_list(self.player_id)
        self.other_friend_list.remove_from_list(self.player_id)
        return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def mark_favorite(self, friend_id):
        if not self.friend_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("FAVORITE_STRANGER")
        if self.favorite_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("FAVORITE_FAVORITE")
        self.favorite_list.add_to_list(friend_id)
        return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def unmark_favorite(self, friend_id):
        if not self.favorite_list.in_list(friend_id):
            return ModifyFriendResultCode.Value("UNFAVORITE_NOT_FAVORITE")
        self.favorite_list.remove_from_list(friend_id)
        return ModifyFriendResultCode.Value("MODIFY_SUCCESS")

    def get_friends_info(self):
        resp = GetFriendsInfoRep()
        resp.friends_list.extend(self.friend_list.to_proto_list())
        resp.send_pending_list.extend(self.send_list.to_proto_list())
        resp.receive_pending_list.extend(self.receive_list.to_proto_list())
        resp.result_code = GetFriendsInfoResultCode.Value(
            "GET_FRIEND_INFO_SUCCESS")
        return resp

    def get_friend_list(self):
        return self.friend_list.get_list()

    def get_favorite_list(self):
        return self.favorite_list.get_list()
