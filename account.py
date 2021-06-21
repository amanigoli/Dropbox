from google.appengine.ext import ndb


class File(ndb.Model):
    account = ndb.KeyProperty(kind='Account')
    name = ndb.StringProperty()
    path = ndb.StringProperty()
    directory = ndb.KeyProperty(kind='Directory')
    blob = ndb.BlobKeyProperty()
    size = ndb.IntegerProperty()
    content = ndb.StringProperty()
    created = ndb.DateTimeProperty()


class Directory(ndb.Model):
    account = ndb.KeyProperty(kind='Account')
    name = ndb.StringProperty()
    path = ndb.StringProperty()
    directory = ndb.KeyProperty(kind='Directory')
    folders = ndb.KeyProperty(kind='Directory', repeated=True)
    files = ndb.KeyProperty(kind=File, repeated=True)
    size = ndb.IntegerProperty()


class Account(ndb.Model):
    root = ndb.KeyProperty(kind=Directory)
    size = ndb.IntegerProperty()
    session = ndb.JsonProperty()
