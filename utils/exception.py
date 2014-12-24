
class InvalidPurchaseItem(Exception):
    def message(self):
        return "Invalud Purchase Item, %s" % super(Exception, self)


class UnsupportedPlayerAction(Exception):
    pass


class UnsupportedFriendAction(Exception):
    pass


class CreatureDisabledAction(Exception):
    def __init__(self, *args, **kwargs):
        slug = kwargs.get("slug")
        action = kwargs.get("action") or ""
        data = {"slug": slug, "action": action.capitalize()}
        msg = "%(action)s is disabled for creature: %(slug)s" % data
        super(CreatureDisabledAction, self).__init__(msg)


class ModelParentKeyMissingValue(Exception):
    def __init__(self, parent_key):
        msg = "Must specify %s since it is the parent key." % parent_key
        super(ModelParentKeyMissingValue, self).__init__(msg)


class NotEnoughEnergy(Exception):
    def __init__(self, player_id, current_energy, consume_energy):
        msg = ("Player(%s) only have %s energy, but want consume %s energy"
               % (player_id, current_energy, consume_energy))
        super(NotEnoughEnergy, self).__init__(msg)
