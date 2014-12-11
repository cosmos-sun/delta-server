# TODO use simplejson/ujson to replace json
import json
import urllib2
from M2Crypto import RSA, EVP
from datetime import datetime
from utils.protocol_pb2 import OS_TYPE
from utils.protocol_pb2 import PURCHASE_RESULT_CODE
from utils.protocol_pb2 import TransactionInfo
from models.transaction import PurchaseTransaction

from utils import log

# TODO move this to settings/config
# live
# INAPP_PURCHASE_VERIFY_URL = 'https://buy.itunes.apple.com/verifyReceipt'
INAPP_PURCHASE_VERIFY_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'
INAPP_PURCHASE_SANDBOX_VERIFY_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'
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
        # TODO Give reward
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
            result_code = PURCHASE_RESULT_CODE.Value("DUPLICATE_PURCHASE")
            msg = "Duplicate transaction."
        else:
            trans = self.create_trans(user_id, trans_kwargs)
            result, result_code = self.verify(**verify_kwargs)
            if result:
                if self.give_reward(user_id, product_info):
                    self.update_trans_status(trans, TRANS_STATUS["PURCHASED"])
                    result_code = PURCHASE_RESULT_CODE.Value(
                        "SUCCESS_PURCHASED")
                    msg = "Purchase successful done."
                else:
                    self.update_trans_status(trans, TRANS_STATUS["UNPAID"])
                    result_code = PURCHASE_RESULT_CODE.Value("SUCCESS_UNPAID")
                    msg = "Failed to reward player."
            else:
                self.update_trans_status(trans, TRANS_STATUS["FAILED"])
                msg = "Failed to verify with third party."
        trans_info.result_code = result_code
        trans_info.msg = msg
        trans_info.product_info = product_info
        return trans_info


class IAPTransaction(BaseTransaction):
    os_type = OS_TYPE.Value("IOS")
    trans_type = "IAP"

    def _send_verify(self, url, trans_receipt, timeout):
        payload = json.dumps({'receipt-data': trans_receipt})
        req = urllib2.Request(url, payload)
        resp = urllib2.urlopen(req, timeout=timeout)
        resp = json.load(resp.read())
        return resp

    def do_verify(self, trans_receipt, timeout=10):
        url = INAPP_PURCHASE_SANDBOX_VERIFY_URL
        resp = self._send_verify(url, trans_receipt, timeout)
        if 21007 == resp.get("status"):
            # player use an sendbox account
            # TODO add log
            resp = self._send_verify(INAPP_PURCHASE_SANDBOX_VERIFY_URL,
                                     trans_receipt, timeout)
        return resp

    def verify(self, receipt=None):
        trans_receipt = receipt
        trans = json.loads(trans_receipt)
        result = True
        result_code = PURCHASE_RESULT_CODE.Value("UNKNOWN")
        try:
            resp = self.do_verify(trans_receipt)
        except Exception, e:
            # TODO - log exception
            msg = str(e)
        else:
            if 21005 == resp.get("status") or resp.get("status") is None:
                result = False
                result_code = PURCHASE_RESULT_CODE.Value("APPLE_BUSY")
            else:
                receipt_resp = resp.get("receipt")
                if (resp.get("status") != 0 or receipt_resp is None or
                    trans.get('skproduct_id') != receipt_resp.get('product_id')
                    or trans.get('transaction_id') !=
                        receipt_resp.get('transaction_id')):
                    result = False
                    result_code = PURCHASE_RESULT_CODE.Value("IAP_THIEF")
        return result, result_code

    def handle_purchase(self, user_id, product_info, msg):
        # use receipt as the trans id
        kwargs = {"receipt": msg.receipt}
        trans = self.handle_transaction(user_id, product_info, kwargs, kwargs)
        return [trans]


class IABTransaction(BaseTransaction):
    os_type = OS_TYPE.Value("Android")
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
            return True, PURCHASE_RESULT_CODE.Value("SUCCESS_PURCHASED")
        except Exception as e:
            # TODO - handle error code
            return False, PURCHASE_RESULT_CODE.Value("UNKNOWN")

    def handle_purchase(self, user_id, product_info, msg):
        trans_list = []
        signatures_list = msg.signature_list
        signed_data_list = msg.signed_data_list
        if len(signatures_list) != len(signed_data_list):
            return_code = PURCHASE_RESULT_CODE.Value("IAB_CHEATER")
            return return_code, "Signatures not match signed data."
        for signed_data, signature in zip(signed_data_list, signatures_list):
            # use order_id as trans_id
            order = json.load(signed_data)
            order_id = order.get("orderId")
            # TODO - do we need notificationId/purchaseToken in trans_info?
            trans_kwargs = {"order_id": order.get("orderId")}
            verify_kwargs = {"signed_data": signed_data,
                             "signature": signature}
            trans = self.handle_transaction(user_id, product_info,
                                            trans_kwargs, verify_kwargs)
            trans_list.append(trans)
        return trans_list
