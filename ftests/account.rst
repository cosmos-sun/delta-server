====================
Account system tests
====================

  >>> def mock_account(name, device_id):
  ...    a = LoginAccount()
  ...    a.device_id = device_id
  ...    a.name = name
  ...    a.type = SignType.Value("DEVICE")
  ...    a.info.os_type = OSType.Value("IOS")
  ...    return a

Mock up account data and log into game:

  >>> account = mock_account("John Doe", "John iPhone")
  >>> msg = LoginAccountRep.FromString(post_message(account, "account"))

Verify that results from server matches:

  >>> player = msg.player_info
  >>> player.name
  u'John Doe'
  >>> player.userId == session_id_to_player_id(msg.session_id)
  True
  >>> len(player.creaturebox) == len(GameRule.default_player_settings.get("creatures"))
  True

Link device to...

  >>> device_link = DeviceLink(device_id="John iPhone").load()
  >>> device_link.exist()
  True
  >>> device_link.player_id == player.userId
  True
