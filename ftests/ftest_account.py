from base import BaseFtest
from actors.account import LinkAccount as LinkAccountActor
from models.content import GameRule
from models.player import DeviceLink
from models.player import Player
from models.player import id_count
from utils.protocol_pb2 import LinkAccount
from utils.protocol_pb2 import LinkAccountRep
from utils.protocol_pb2 import LinkAccountResultCode
from utils.protocol_pb2 import LoginAccountResultCode
from utils.protocol_pb2 import SignType


class LoginAccountFtest(BaseFtest):
    def testLoginAccount(self):
        expected_player_id = (id_count.load() or 0) + 1
        name = "happylatte"
        device_id1 = "TEST_LOGIN_ACCOUNT_1"
        device_id2 = "TEST_LOGIN_ACCOUNT_2"
        agc_id1 = "test_login_agc1"
        agc_id2 = "test_login_agc2"
        gc_id = "test_login_gc"

        # Login with device id only
        session_id1, msg = self.create_player(device_id1, name)
        self.assertEquals(msg.result_code,
                          LoginAccountResultCode.Value("LOGIN_ACC_SUCCESS"))
        player_id = msg.player_info.userId
        self.assertEquals(player_id, expected_player_id)
        self.player_ids.add(player_id)
        self.assertEquals(player_id,
                          self.session_id_to_player_id(session_id1))
        self.assertEquals(name, msg.player_info.name)
        default_creatures = GameRule.default_player_settings.get("creatures")
        self.assertEquals(len(msg.player_info.creaturebox),
                          len(default_creatures))
        device_l1 = DeviceLink(device_id=device_id1).load()
        self.assertTrue(device_l1.exist())
        self.assertEquals(device_l1.player_id, player_id)

        # Login with pre_device_id
        session_id2, msg = self.create_player(device_id=device_id2,
                                              name=name,
                                              pre_device_id=device_id1)
        self.assertEquals(player_id,
                          self.session_id_to_player_id(session_id2))
        # old session id been removed
        self.assertIsNone(self.session_id_to_player_id(session_id1))
        device_l1 = DeviceLink(device_id=device_id1)
        self.assertFalse(device_l1.exist())
        device_l2 = DeviceLink(device_id=device_id2).load()
        self.assertTrue(device_l2.exist())
        self.assertEquals(device_l2.player_id, player_id)
        # device_id in player models not modified
        player = Player(id=player_id).load()
        self.assertEquals(player.device_id, device_id1)

        # Login with pip id and sign_type is AGC
        # - will create a new player and link device_id2 to the new player
        _, msg = self.create_player(device_id=device_id2, name=name,
                                    sign_type=SignType.Value("APPLE"),
                                    pip_id=agc_id1)
        player_id2 = msg.player_info.userId
        player2 = Player(id=player_id2).load()
        self.assertNotEquals(player_id2, player_id)
        self.assertEquals(player2.agc_id, agc_id1)
        device_l2 = DeviceLink(device_id=device_id2).load()
        self.assertEquals(device_l2.player_id, player_id2)

        # Login with pre_device_id another pip id
        # - update device to new device_id and create a new player.
        _, msg = self.create_player(device_id=device_id1, name=name,
                                    sign_type=SignType.Value("APPLE"),
                                    pip_id=agc_id2, pre_device_id=device_id2)
        player_id3 = msg.player_info.userId
        player3 = Player(id=player_id3).load()
        self.assertNotEquals(player_id2, player_id3)
        self.assertNotEquals(player_id3, player_id)
        self.assertEquals(player3.agc_id, agc_id2)
        device_l2 = DeviceLink(device_id=device_id2)
        self.assertFalse(device_l2.exist())
        device_l1 = DeviceLink(device_id=device_id1).load()
        self.assertTrue(device_l1.exist())
        self.assertEquals(device_l1.player_id, player_id3)

        # Login with pip_id and sign_type is GC
        _, msg = self.create_player(device_id=device_id1, name=name,
                                    sign_type=SignType.Value("GOOGLE"),
                                    pip_id=gc_id)
        player_id4 = msg.player_info.userId
        player4 = Player(id=player_id4).load()
        self.assertNotEquals(player_id3, player_id4)
        self.assertNotEquals(player_id2, player_id4)
        self.assertNotEquals(player_id, player_id4)
        self.assertEquals(player4.gc_id, gc_id)
        self.assertIsNone(player4.agc_id)
        device_l1 = DeviceLink(device_id=device_id1).load()
        self.assertTrue(device_l1.exist())
        self.assertEquals(device_l1.player_id, player_id4)

        # Facebook can't login for now
        _, msg = self.create_player(device_id=device_id1, name=name,
                                    sign_type=SignType.Value("FACEBOOK"),
                                    pip_id="123")
        self.assertEquals(msg.result_code, LoginAccountResultCode.Value(
            "LOGIN_ACC_DISABLED_SIGN_TYPE"))

    def testLinkAccount(self):
        device_id = "test_link_account_device"
        session_id, msg = self.create_player(device_id=device_id)
        player_id = msg.player_info.userId
        player = Player(id=player_id).load()

        l_acc = LinkAccount()
        for sign_type, handler in LinkAccountActor.link_acc_map.iteritems():
            attr_name = handler.player_index
            self.assertIsNone(getattr(player, attr_name))

            # Try link from an device not exist
            pip_id1 = "123"
            l_acc.type = sign_type
            l_acc.pip_id = pip_id1
            l_acc.device_id = "link_account_not_exist_one"
            msg = self.post_message(l_acc, LinkAccountRep,
                                    session_id=session_id)
            self.assertEquals(msg.result_code,
                              LinkAccountResultCode.Value("LINK_ACC_OTHER"))
            player.load()
            self.assertIsNone(getattr(player, attr_name))

            # link
            l_acc.device_id = device_id
            msg = self.post_message(l_acc, LinkAccountRep,
                                    session_id=session_id)
            self.assertEquals(msg.result_code,
                              LinkAccountResultCode.Value("LINK_ACC_OTHER"))
            player.load()
            self.assertEquals(str(getattr(player, attr_name)), pip_id1)

            # try link another
            pip_id2 = "1234"
            l_acc.pip_id = pip_id2
            msg = self.post_message(l_acc, LinkAccountRep,
                                    session_id=session_id)
            self.assertEquals(msg.result_code, LinkAccountResultCode.Value(
                "LINK_ACC_DIFFERENT_PIP"))
            player.load()
            self.assertEquals(str(getattr(player, attr_name)), pip_id1)

        # unsupported sign type
        for sign_type in set(SignType.values()) - \
                set(LinkAccountActor.link_acc_map.keys()):
            l_acc.type = sign_type

            msg = self.post_message(l_acc, LinkAccountRep,
                                    session_id=session_id)
            self.assertEquals(msg.result_code,
                              LinkAccountResultCode.Value("LINK_ACC_OTHER"))
