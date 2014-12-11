import re, urllib, urllib2, csv, json, base64

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))

from utils import protocol_pb2
import models
from models.content import Content, OID
from utils import log


def build_enum_type(name):
    return '_' + name.upper()

def assign_value(inst, data):
    for name, value in inst.DESCRIPTOR.fields_by_name.items():
        if name not in data:
            continue
        attr = getattr(inst, name)
        if hasattr(attr, 'DESCRIPTOR'):
            assign_value(attr, data[name])
        else:
            if type(data[name]) is list:
                l = []
                if hasattr(value.message_type, 'name') and getattr(value.message_type, 'name') is not None:
                    cls = getattr(protocol_pb2, value.message_type.name)
                    for d in data[name]:
                        sub_inst = cls()
                        assign_value(sub_inst, d)
                        l.append(sub_inst)
                else:
                    for d in data[name]:
                        l.append(d)
                getattr(inst, name).extend(l)
            else:
                if hasattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') and getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type') is not None:
                        enum_type = getattr(inst.DESCRIPTOR.fields_by_name[name], 'enum_type').name
                        enum_inst = getattr(protocol_pb2, build_enum_type(enum_type))
                        d = enum_inst.values_by_name[data[name]].number
                        setattr(inst, name, d)
                else:
                    setattr(inst, name, data[name])


class NaviSheet(object):
    def __init__(self, key, gid, client):
        super(NaviSheet, self).__init__()
        self.key = key
        self.gid = gid
        self.cls_name = 'Navi'
        self.rows = None
        self.client = client

    def download(self):
        self.rows = self.client.download(self)

    def extract(self, live=True):
        rows = self.rows[1:]
        content = Content(version_id=OID)
        for r in rows:
            ds = DataSheet(r[0], r[1], r[2])
            ds.download_sheet(self.client)
            ds.extract_sheet()
            if r[0] == "World":
                content.world = ds.insts[0]
            elif r[0] == "CreatureType":
                content.creature_types = ds.insts
        content.store()

    def extract_live(self):
        self.download()
        self.extract()

    def extract_local(self):
        import glob
        fs = glob.glob('*.csv')
        content = Content(version_id=OID)
        for f in fs:
            if f == 'Navi.csv': continue
            cls = f.split('.')[0]

            if cls == "World":
                ds = DataSheet(cls, None, None)
                data = open(f).readlines()
                ds.local_sheet(data)
                ds.extract_sheet()
                content.world = ds.insts[0]
            elif cls == "CreatureType":
                ds = DataSheet(cls, None, None)
                data = [row[0] for row in csv.reader(open(f))]
                ds.local_sheet(data)
                ds.extract_sheet()
                content.creature_types = ds.insts
        content.store()


class DataSheet(object):
    def __init__(self, cls_name, key, gid):
        super(DataSheet, self).__init__()
        self.key = key
        self.gid = gid
        self.cls_name = cls_name
        self.proto_cls = getattr(protocol_pb2, cls_name)
        self.insts = []
        self.rows = None

    def download_sheet(self, client):
        self.rows = [i[0] for i in client.download(self)]

    def local_sheet(self, data):
        self.rows = data

    def extract_sheet(self):
        for row in self.rows:
            inst = self.proto_cls()
            assign_value(inst, json.loads(row))
            self.insts.append(base64.b64encode(inst.SerializeToString()))

class Client(object):
    def __init__(self, email, password):
        super(Client, self).__init__()
        self.email = email
        self.password = password

    def _get_auth_token(self, email, password, source, service):
        url = "https://www.google.com/accounts/ClientLogin"
        params = {
            "Email": email, "Passwd": password,
            "service": service,
            "accountType": "HOSTED_OR_GOOGLE",
            "source": source
        }
        req = urllib2.Request(url, urllib.urlencode(params))
        return re.findall(r"Auth=(.*)", urllib2.urlopen(req).read())[0]

    def get_auth_token(self):
        source = type(self).__name__
        return self._get_auth_token(self.email, self.password, source, service="wise")

    def download(self, spreadsheet, fmt="csv"):
        url_format = "https://spreadsheets.google.com/feeds/download/spreadsheets/Export?key=%s&exportFormat=%s&gid=%i"
        headers = {
            "Authorization": "GoogleLogin auth=" + self.get_auth_token(),
            "GData-Version": "3.0"
        }
        log.info(url_format % (spreadsheet.key, fmt, int(spreadsheet.gid)))
        req = urllib2.Request(url_format % (spreadsheet.key, fmt, int(spreadsheet.gid)), headers=headers)
        csv_file = urllib2.urlopen(req)
        ret = []
        with open('content/csv/%s.csv' % spreadsheet.cls_name, 'w') as w:
            writer = csv.writer(w)
            for row in csv.reader(csv_file):
                writer.writerow(row)
                ret.append(row)
        return ret

def main(from_live=True):
    log.info('Start extract content data.')
    content_navi_key = '1lt2HRMmU0KvWFbJN0MHppZmFh6nesNXT7VgYwFyjvho'
    content_navi_gid = '1866003486'

    # Create client and spreadsheet objects
    client = Client('hugo@happylatte.com', '12356zao')

    navi = NaviSheet(content_navi_key, content_navi_gid, client)
    if from_live:
        navi.extract_live()
    else:
        navi.extract_local()
    log.info('Finish extract content data.')

if __name__ == "__main__":
    main()