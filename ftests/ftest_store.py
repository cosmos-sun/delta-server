from base import BaseFtest
from models.player import Player
from utils.protocol_pb2 import GetProductsResultCode
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import ProductsReq
from utils.protocol_pb2 import ProductsResp
from utils.settings import PURCHASE_ITEMS


class PurchaseStoreFtest(BaseFtest):
    def testGetProductsList(self):
        def _verify_products(products, p_settings):
            for p in products:
                p_s = p_settings.get(p.pid)
                self.assertEquals(p.quantity, p_s.get("quantity"))
                self.assertEquals(p.price, p_s.get("price"))
                self.assertEquals(p.currency, p_s.get("currency"))

        session_id, msg = self.create_player(os_type=OSType.Value("IOS"))
        req = ProductsReq()
        resp = self.post_message(req, ProductsResp, session_id=session_id)
        self.assertEquals(resp.result_code,
                          GetProductsResultCode.Value("GET_PRODUCTS_SUCCESS"))
        iap = PURCHASE_ITEMS.get(OSType.Value("IOS"))
        _verify_products(resp.products, iap)

        # update player os_type to Android
        player = Player(id=msg.player_info.userId)
        player.load()
        player.os_type = OSType.Value("Android")
        player.store()

        resp = self.post_message(req, ProductsResp, session_id=session_id)
        self.assertEquals(resp.result_code,
                          GetProductsResultCode.Value("GET_PRODUCTS_SUCCESS"))
        iab = PURCHASE_ITEMS.get(OSType.Value("Android"))
        _verify_products(resp.products, iab)
