import re, urllib, urllib2, csv, glob

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
from models.content import Content, OID
from utils import log

file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv/*.csv')

class NaviSheet(object):
    def __init__(self, key, gid, client):
        super(NaviSheet, self).__init__()
        self.key = key
        self.gid = gid
        self.cls_name = 'Navi'
        self.rows = []
        self.client = client

    def download(self):
        csv_file = self.client.download(self)
        with open('content/csv/%s.csv' % self.cls_name, 'w') as w:
            writer = csv.writer(w)
            for row in csv.reader(csv_file):
                writer.writerow(row)
                self.rows.append(row)
        rows = self.rows[1:]
        for r in rows:
            ds = DataSheet(r[0], r[1], r[2])
            ds.download(self.client)

    def extract(self):
        fs = glob.glob(file_path)
        content = Content(version_id=OID)
        for f in fs:
            cls = f.split('/')[-1].split('.')[0]
            if cls == 'Navi': continue
            if cls == "Configs":
                data = open(f).readlines()
                content.world = data[0]
                content.configs = data[1]
            elif cls == "CreatureType":
                data = [line.rstrip() for line in open(f).readlines()]
                content.creature_types = data
        content.store()


class DataSheet(object):
    def __init__(self, cls_name, key, gid):
        super(DataSheet, self).__init__()
        self.key = key
        self.gid = gid
        self.cls_name = cls_name

    def download(self, client):
        csv_file = client.download(self)
        with open(file_path.replace('*', self.cls_name), 'w') as w:
            for row in csv.reader(csv_file):
                row = row[0]
                w.write(row + '\n')

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
        return csv_file

def main(action='live'):
    log.info('Start extract content data.')
    content_navi_key = '1lt2HRMmU0KvWFbJN0MHppZmFh6nesNXT7VgYwFyjvho'
    content_navi_gid = '1866003486'

    # Create client and spreadsheet objects
    client = Client('hugo@happylatte.com', '12356zao')

    navi = NaviSheet(content_navi_key, content_navi_gid, client)
    if action == 'live':
        navi.download()
        navi.extract()
        return

    if action == 'download':
        navi.download()
    if action == 'extract':
        navi.extract()

    log.info('Finish extract content data.')

if __name__ == "__main__":
    action = 'live'
    if len(sys.argv) == 2:
        action = sys.argv[1]
    main(action)