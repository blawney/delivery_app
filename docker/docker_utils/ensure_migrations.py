import os
import sys

# first arg is the path to the app's root.  That is, if we ran ls <app root> we would see manage.py, etc.
sys.path.append(sys.argv[1])
os.chdir(sys.argv[1])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sequencing_delivery.settings")
import django
from django.conf import settings

MIGRATION_DIR = 'migrations'

def touch(filepath):
        with open(filepath, 'a'):
                os.utime(filepath, None)

for app in settings.INSTALLED_APPS:
        if os.path.isdir(app):
                print 'yes-%s' % app
                expected_dir = os.path.join(app, MIGRATION_DIR)
                expected_file = os.path.join(expected_dir,'__init__.py')
                if os.path.isdir(expected_dir):
                        if not os.path.isfile(expected_file):
                                touch(expected_file)
                else:
                        os.mkdir(expected_dir)
                        touch(expected_file)
