from dal.base import *
from utils.exception import InvalidPurchaseItem
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import ProductInfo
from utils.settings import PURCHASE_ITEMS


class PurchaseItem(Base):
    p_id = TextAttr()
    price = IntAttr()
    currency = TextAttr()
    quantity = IntAttr()
    _oid_key = "p_id"

    def __init__(self, p_id, price=None, currency=None, quantity=None):
        if not p_id:
            raise InvalidPurchaseItem("Missing pid")
        if not price:
            raise InvalidPurchaseItem("Missing price")
        if not currency:
            raise InvalidPurchaseItem("Missing currency")
        if not quantity:
            raise InvalidPurchaseItem("Missing quantity")
        super(PurchaseItem, self).__init__(p_id=p_id, price=price,
                                           currency=currency,
                                           quantity=quantity)

    def to_protocal(self):
        proto = ProductInfo()
        proto.pid = self.p_id
        proto.price = self.price
        proto.currency = self.currency
        proto.quantity = self.quantity
        return proto


class ProductsList(object):
    # os_type_products_map = {os_type: [product_item1, product_item2, ...]}
    # product_info_map = {product_id1: product_item1,
    #                     product_id2: product_item2}
    supported_os_type = OSType.values()
    os_type_products_map = {}
    product_info_map = {}
    __instance = None

    @classmethod
    def instance(cls):
        # Use instance to ensure purchase items been loaded.
        if not cls.__instance:
            cls.__instance = cls()
            for os_type, products in PURCHASE_ITEMS.iteritems():
                products_list = []
                for p_id, item_attr in products.iteritems():
                    purchase_item = PurchaseItem(p_id, **item_attr)
                    products_list.append(purchase_item.to_protocal())
                    cls.__instance.product_info_map[p_id] = purchase_item
                cls.__instance.os_type_products_map[os_type] = products_list
        return cls.__instance

    @classmethod
    def is_valid_os_type(cls, os_type):
        return os_type in cls.supported_os_type

    def get_products_list(self, os_type):
        return self.os_type_products_map.get(os_type)

    def get_product_info(self, product_id):
        return self.product_info_map.get(product_id)