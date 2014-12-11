from base_actor import ChildActor
from utils.protocol_pb2 import GET_PRODUCTS_CODE
from utils.protocol_pb2 import OS_TYPE
from utils.protocol_pb2 import PURCHASE_RESULT_CODE
from utils.protocol_pb2 import ProductsResp
from utils.protocol_pb2 import PurchaseResp
from utils.protocol_pb2 import TransactionInfo
from models.products_list import ProductsList
from actors.transaction import IABTransaction
from actors.transaction import IAPTransaction

from utils import log

class ProductsListActor(ChildActor):
    purchase_handle_map = {
        OS_TYPE.Value("IOS"): IAPTransaction(),
        OS_TYPE.Value("Android"): IABTransaction(),
    }

    def ProductsReq(self, msg):
        user_id = self.parent.pid
        resp = ProductsResp()
        if user_id:
            # TODO get os_type by getPlayerInfo
            #player_info = getPlayerInfo(user_id)
            # if player_info:
            #     os_type = player_info.os_type
            #     if ProductsList.is_valid_os_type(os_type):
            #         resp.result_code = GET_PRODUCTS_CODE.Value(
            #             "GET_PRODUCTS_SUCCESS")
            #         resp.products = ProductsList().get_products_list(os_type)
            #     else:
            #         resp.result_code = GET_PRODUCTS_CODE.Value(
            #             "NOT_SUPPORTED_DEVICE")
            # else:
            #     resp.result_code = GET_PRODUCTS_CODE.Value(
            #            "INVALID_PLAYER_ID")
            import random
            os_type = random.choice(OS_TYPE.values())
            if ProductsList.is_valid_os_type(os_type):
                resp.result_code = GET_PRODUCTS_CODE.Value("GET_PRODUCTS_SUCCESS")
                resp.products = ProductsList.instance(
                    ).get_products_list(os_type)
            else:
                resp.result_code = GET_PRODUCTS_CODE.Value("NOT_SUPPORTED_DEVICE")
        else:
            resp.result_code = GET_PRODUCTS_CODE.Value("INVALID_PLAYER_ID")
        self.resp(resp)

    def PurchaseReq(self, msg):
        resp = PurchaseResp()
        user_id = self.parent.pid
        product_id = msg.product_id
        p_info = ProductsList.instance().get_product_info(product_id)
        if not p_info:
            trans_info = TransactionInfo()
            trans_info.result_code = PURCHASE_RESULT_CODE.Value("INVALID_PRODUCT_ID")
            resp.trans_infos = [trans_info]
        else:
            handler = self.purchase_handle_map.get(p_info.os_type)
            resp.trans_infos = handler.handle_purchase(user_id, p_info, msg)
        self.resp(resp)