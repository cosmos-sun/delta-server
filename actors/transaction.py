import simplejson
import urllib2
from M2Crypto import RSA, EVP
from datetime import datetime
from utils.protocol_pb2 import OSType
from utils.protocol_pb2 import PurchaseResultCode
from utils.protocol_pb2 import TransactionInfo
from utils.settings import INAPP_PURCHASE_VERIFY_URL
from utils.settings import INAPP_PURCHASE_SANDBOX_VERIFY_URL
from models.player import Player
from models.transaction import PurchaseTransaction

from utils import log


TRANS_STATUS = {'STARTED': 1,
                "PURCHASED": 2,
                "UNPAID": 3,
                "FAILED": 4}


class BaseTransaction(object):
    os_type = None
    trans_type = None

    def duplicate_trans(self, trans_kw):
        trans_kw.update({"trans_type": self.trans_type})
        trans = PurchaseTransaction(**trans_kw)
        exist_trans = PurchaseTransaction(trans.oid).load()
        return exist_trans

    def create_trans(self, user_id, **kw):
        kw.update({"player_id": user_id,
                   "status": TRANS_STATUS['STARTED'],
                   "start_time": datetime.now(),
                   "trans_type": self.trans_type})
        trans = PurchaseTransaction(**kw)
        trans.store()
        return trans

    def give_reward(self, user_id, product_info):
        qt = product_info.get("quantity")
        player = Player(id=user_id)
        if player.exist():
            player.load()
            player.gems += qt
            player.store()
            log.info("%s purchase - add %s gems to player(%s)" %
                     (self.os_type, qt, user_id))
        return True

    def update_trans_status(self, trans, status):
        trans.status = status
        trans.handle_time = datetime.now()
        trans.store()
        return True

    def handle_purchase(self, user_id, product_info, msg):
        raise NotImplementedError

    def verify(self, **kwargs):
        raise NotImplementedError

    def handle_transaction(self, user_id, product_info,
                           trans_kwargs, verify_kwargs):
        trans_info = TransactionInfo()
        for key, val in trans_kwargs.iteritems():
            setattr(trans_info, key, val)
        if self.duplicate_trans(**trans_kwargs):
            # TODO handle retry from client.
            result_code = PurchaseResultCode.Value("DUPLICATE_PURCHASE")
            msg = "Duplicate transaction."
        else:
            trans = self.create_trans(user_id, trans_kwargs)
            result, result_code = self.verify(**verify_kwargs)
            log_data = {"player_id": user_id,
                        "purchase_type": self.trans_type,
                        "product_info": product_info}
            if result:
                if self.give_reward(user_id, product_info):
                    self.update_trans_status(trans, TRANS_STATUS["PURCHASED"])
                    result_code = PurchaseResultCode.Value("SUCCESS_PURCHASED")
                    msg = "Purchase successful done."
                    log.info("Purchase successfully done: %s" % str(log_data))
                else:
                    self.update_trans_status(trans, TRANS_STATUS["UNPAID"])
                    result_code = PurchaseResultCode.Value("SUCCESS_UNPAID")
                    msg = "Failed to reward player."
                    log.info("Purchase unpaid: %s" % str(log_data))
            else:
                self.update_trans_status(trans, TRANS_STATUS["FAILED"])
                msg = "Failed to verify with third party."
                log.info("Purchase verify failed: %s" % str(log_data))
        trans_info.result_code = result_code
        trans_info.msg = msg
        trans_info.product_info.CopyFrom(product_info.to_protocal())
        return trans_info


class IAPTransaction(BaseTransaction):
    os_type = OSType.Value("IOS")
    trans_type = "IAP"

    def _send_verify(self, url, trans_receipt, timeout):
        payload = simplejson.dumps({'receipt-data': trans_receipt})
        req = urllib2.Request(url, payload)
        resp = urllib2.urlopen(req, timeout=timeout)
        resp = simplejson.load(resp.read())
        return resp

    def do_verify(self, trans_receipt, timeout=10):
        url = INAPP_PURCHASE_VERIFY_URL
        resp = self._send_verify(url, trans_receipt, timeout)
        if 21007 == resp.get("status"):
            # player use an sendbox account
            log_data = {"player_id": self.player_id,
                        "resp": resp,
                        "receipt": trans_receipt}
            log.warning("IAP - Player use an sendbox account: %s"
                        % str(log_data))
            resp = self._send_verify(INAPP_PURCHASE_SANDBOX_VERIFY_URL,
                                     trans_receipt, timeout)
        return resp

    def verify(self, receipt=None):
        trans_receipt = receipt
        trans = simplejson.loads(trans_receipt)
        result = True
        result_code = PurchaseResultCode.Value("UNKNOWN")
        try:
            resp = self.do_verify(trans_receipt)
        except Exception, e:
            log.error("IAP - verify exception: %s" % str(e))
        else:
            if 21005 == resp.get("status") or resp.get("status") is None:
                result = False
                result_code = PurchaseResultCode.Value("APPLE_BUSY")
            else:
                receipt_resp = resp.get("receipt")
                if (resp.get("status") != 0 or receipt_resp is None or
                    trans.get('skproduct_id') != receipt_resp.get('product_id')
                    or trans.get('transaction_id') !=
                        receipt_resp.get('transaction_id')):
                    result = False
                    result_code = PurchaseResultCode.Value("IAP_THIEF")
        return result, result_code

    def handle_purchase(self, user_id, product_info, msg):
        # use receipt as the trans id
        self.player_id = user_id
        kwargs = {"receipt": msg.receipt}
        trans = self.handle_transaction(user_id, product_info, kwargs, kwargs)
        return [trans]


class IABTransaction(BaseTransaction):
    os_type = OSType.Value("Android")
    trans_type = "IAB"

    def verify(self, signed_data=None, signature=None):
        # sined data and signature may unicode from client,
        # format it as normal string.
        signed_data = str(signed_data)
        signature = str(signature)

        # TODO - update iab public key
        pem_file = "certificate/iab_public_key.pem"
        rsa = RSA.load_pub_key(pem_file)

        pubkey = EVP.PKey()
        pubkey.assign_rsa(rsa)
        pubkey.reset_context(md='sha1')
        pubkey.verify_init()
        try:
            pubkey.verify_update(signed_data)

            signature_padded = signature
            if signature_padded:
                while len(signature_padded) % 4 != 0:
                    signature_padded += '='
            signature_decoded = signature_padded.decode('base64')
            assert pubkey.verify_final(signature_decoded) == 1
            return True, PurchaseResultCode.Value("SUCCESS_PURCHASED")
        except Exception as e:
            # TODO - handle error code
            return False, PurchaseResultCode.Value("UNKNOWN")

    def handle_purchase(self, user_id, product_info, msg):
        trans_list = []
        signatures_list = msg.signature_list
        signed_data_list = msg.signed_data_list
        if len(signatures_list) != len(signed_data_list):
            return_code = PurchaseResultCode.Value("IAB_CHEATER")
            return return_code, "Signatures not match signed data."
        for signed_data, signature in zip(signed_data_list, signatures_list):
            # use order_id as trans_id
            order = simplejson.load(signed_data)
            order_id = order.get("orderId")
            # TODO - do we need notificationId/purchaseToken in trans_info?
            trans_kwargs = {"order_id": order.get("orderId")}
            verify_kwargs = {"signed_data": signed_data,
                             "signature": signature}
            trans = self.handle_transaction(user_id, product_info,
                                            trans_kwargs, verify_kwargs)
            trans_list.append(trans)
        return trans_list
