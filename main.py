import os

import webapp2
import jinja2
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.blobstore import blobstore
from google.appengine.ext.webapp import blobstore_handlers

from python.account import Account, Directory, File

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + '/../html'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)

JINJA_ENVIRONMENT.add_extension('jinja2.ext.do')


def readable_bytes(size, precision=2):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size = size / 1024.0
    return "%.*f %s" % (precision, size, suffixes[suffixIndex])


def get_duplicates(name, size, path):
    account = MainHandler.query_account(users.get_current_user().email())
    duplicates = File.query(File.account == account.key, File.name == name, File.size == size,
                            File.path != path).fetch()

    return duplicates


class MainHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/'))
            return

        account = self.query_account(user.email())
        if not account:
            account = self.create_account(user.email())

        directory_key = self.request.get('directory_key')

        if not directory_key:
            directory = account.root.get()
        else:
            directory = ndb.Key(urlsafe=directory_key).get()

        template_values = {
            'logout_url': users.create_logout_url(self.request.uri),
            'user': user,
            'account': account,
            'directory': directory,
            'upload_file': blobstore.create_upload_url('/upload_file'),
            'readable_bytes': readable_bytes,
            'get_duplicates': get_duplicates,
            'Key': ndb.Key
        }

        template = JINJA_ENVIRONMENT.get_template('main.html')
        self.response.write(template.render(template_values))

    @staticmethod
    def query_account(email):
        return ndb.Key(Account, email).get()

    @staticmethod
    def create_account(email):
        root = Directory()
        root.name = ''
        root.path = ''
        root.size = 0
        root.put()
        account = Account(id=email)
        account.root = root.key
        account.session = {}
        account.size = 0
        account.put()
        return account


class AddDirectoryHandler(webapp2.RequestHandler):
    def post(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()

        name = self.request.get('name')

        account = MainHandler.query_account(users.get_current_user().email())

        if not Directory.query(Directory.account == account.key, Directory.name == name,
                               Directory.path == directory.path + directory.name + '/').fetch():
            dir = Directory()
            dir.account = account.key
            dir.name = name
            dir.path = directory.path + directory.name + '/'
            dir.directory = directory.key
            dir.size = 0
            dir.put()
            directory.folders.append(dir.key)
            directory.put()

        else:
            account.session['direxst'] = 'Directory "{}" Exists'.format(name)
            account.put()

        self.redirect("/?directory_key=" + directory_key)


class RemoveDirectoryHandler(webapp2.RequestHandler):
    def get(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()
        folder_key = self.request.get('folder_key')
        folder = ndb.Key(urlsafe=folder_key).get()

        index = directory.folders.index(folder.key)
        del directory.folders[index]
        directory.put()
        folder.key.delete()

        self.redirect("/?directory_key=" + directory_key)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()

        upload = self.get_uploads()[0]
        blob = blobstore.BlobInfo(upload.key())

        account = MainHandler.query_account(users.get_current_user().email())

        if not File.query(File.account == account.key, File.name == blob.filename,
                          File.path == directory.path + directory.name + '/').fetch():
            file = File()
            file.account = account.key
            file.name = blob.filename
            file.path = directory.path + directory.name + '/'
            file.directory = directory.key
            file.blob = upload.key()
            file.size = blob.size
            file.content = blob.content_type
            file.created = blob.creation
            file.put()
            directory.files.append(file.key)
            directory.size += blob.size
            directory.put()
            account.size += file.size
            account.put()

        else:
            account.session['filexst'] = 'File "{}" Exists'.format(blob.filename)
            account.put()

        self.redirect("/?directory_key=" + directory_key)


class DownloadHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        file = ndb.Key(urlsafe=self.request.get('file_key')).get()
        self.send_blob(file.blob, save_as=file.name)


class RemoveFileHandler(webapp2.RequestHandler):
    def get(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()

        file = ndb.Key(urlsafe=self.request.get('file_key')).get()
        blobstore.delete(file.blob)
        file.key.delete()

        del directory.files[directory.files.index(file.key)]
        directory.size -= file.size
        directory.put()

        account = MainHandler.query_account(users.get_current_user().email())
        account.size -= file.size
        account.put()

        self.redirect("/?directory_key=" + directory_key)


class MoveFileHandler(webapp2.RequestHandler):
    def get(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()

        file = ndb.Key(urlsafe=self.request.get('file_key')).get()

        account = MainHandler.query_account(users.get_current_user().email())
        account.session['move_file'] = file.key.urlsafe()
        account.put()

        self.redirect("/?directory_key=" + directory_key)

    def post(self):
        directory_key = self.request.get('directory_key')
        directory = ndb.Key(urlsafe=directory_key).get()

        if self.request.get('action') == 'cancel':
            account = MainHandler.query_account(users.get_current_user().email())
            del account.session['move_file']
            account.put()

        if self.request.get('action') == 'move':
            account = MainHandler.query_account(users.get_current_user().email())
            file = ndb.Key(urlsafe=account.session['move_file']).get()

            if not File.query(File.account == account.key, File.name == file.name,
                              File.path == directory.path + directory.name + '/').fetch():

                old_directory = file.directory.get()
                del old_directory.files[old_directory.files.index(file.key)]
                old_directory.size -= file.size
                old_directory.put()

                file.path = directory.path + directory.name + '/'
                file.directory = directory.key
                file.put()
                directory.files.append(file.key)
                directory.size += file.size
                directory.put()

                del account.session['move_file']
                account.put()

            else:
                account.session['movexst'] = 'File "{}" Exists'.format(file.name)
                account.put()

        self.redirect("/?directory_key=" + directory_key)


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/add_dir', AddDirectoryHandler),
    ('/remove_dir', RemoveDirectoryHandler),
    ('/upload_file', UploadHandler),
    ('/download_file', DownloadHandler),
    ('/remove_file', RemoveFileHandler),
    ('/move_file', MoveFileHandler),
], debug=True)
