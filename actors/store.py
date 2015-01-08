from base_actor import ChildActor
from base_actor import MessageHandlerWrapper
from utils.protocol_pb2 import GetProductsResultCode
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import PurchaseResultCode
from utils.protocol_pb2 import ProductsResp
from utils.protocol_pb2 import PurchaseResp
from utils.protocol_pb2 import TransactionInfo
from models.products_list import ProductsList
from actors.transaction import IABTransaction
from actors.transaction import IAPTransaction

from utils import log


class ProductsListActor(ChildActor):
    purchase_handle_map = {
        OSType.Value("IOS"): IAPTransaction(),
        OSType.Value("Android"): IABTransaction(),
    }

    @MessageHandlerWrapper(ProductsResp, GetProductsResultCode.Value(
        "GET_PRODUCTS_INVALID_SESSION"))
    def ProductsReq(self, msg):
        player = self.parent.player
        os_type = player.get_os_type()
        resp = ProductsResp()
        if ProductsList.is_valid_os_type(os_type):
            resp.result_code = GetProductsResultCode.Value(
                "GET_PRODUCTS_SUCCESS")
            resp.products.extend(
                ProductsList.instance().get_products_list(os_type))
        else:
            resp.result_code = GetProductsResultCode.Value(
                "NOT_SUPPORTED_DEVICE")
        return self.resp(resp)

    @MessageHandlerWrapper(PurchaseResp, PurchaseResultCode.Value(
        "PURCHASE_INVALID_SESSION"))
    def PurchaseReq(self, msg):
        resp = PurchaseResp()
        user_id = self.parent.pid
        product_id = msg.product_id
        p_info = ProductsList.instance().get_product_info(product_id)
        if not p_info:
            trans_info = TransactionInfo()
            trans_info.result_code = PurchaseResultCode.Value(
                "INVALID_PRODUCT_ID")
            resp.trans_infos.extend([trans_info])
        else:
            handler = self.purchase_handle_map.get(p_info.os_type)
            resp.trans_infos.extend(handler.handle_purchase(
                user_id, p_info, msg))
        return self.resp(resp)