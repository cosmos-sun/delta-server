from boto.dynamodb2.layer1 import DynamoDBConnection
from boto.dynamodb2.table import Table
from boto.dynamodb2.fields import HashKey
from boto.dynamodb2.types import NUMBER
from boto.dynamodb2.items import Item

from dal.base import BaseMeta

conn = DynamoDBConnection(host='localhost', port=8888, aws_secret_access_key='A', is_secure=False)

TABLE_NAMES = set(conn.list_tables()['TableNames'])
TABLES = {}

def _create_table(cls):
    kwargs = dict(table_name=cls.__name__, schema=[HashKey('oid', data_type=NUMBER)], connection=conn)
    if cls.__name__ in TABLE_NAMES:
        table = Table(**kwargs)
    else:
        table = Table.create(**kwargs)
    TABLES[cls.__name__] = table
    return table

def _get_table(cls):
    return TABLES.get(cls.__name__, _create_table(cls))

def load(cls, oid):
    table = _get_table(cls)
    return dict(table.get_item(oid=oid))

def store(cls, oid, data):
    table = _get_table(cls)
    item = Item(table, data=data)
    item.save()
