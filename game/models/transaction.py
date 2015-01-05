from dal.base import *


class PurchaseTransaction(Base):
    trans_id = LongAttr()
    receipt = TextAttr()
    order_id = TextAttr()
    player_id = IntAttr()
    status = IntAttr()
    trans_type = TextAttr()
    start_time = DateTimeAttr()
    handle_time = DateTimeAttr()
    _oid_tpl = "%s_purchase_%s"
    _oid_key = "trans_id"
    _index_attributes = ["player_id"]

    @property
    def oid(self):
        if "IAP" == self.trans_type:
            receipt = self.receipt
        else:
            receipt = self.order_id
        return self._oid_tpl % (self.trans_type, receipt)