import os
import sys

app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(app_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sequencing_delivery.settings')
import django
django.setup()

from django.contrib.auth.models import User
from ConfigParser import SafeConfigParser

class MissingApplicationConfig(Exception):
	pass

class InvalidEnvironment(Exception):
	pass

config_parser = SafeConfigParser()
config_file = os.getenv('APP_CONFIG')
status = os.getenv('APP_STATUS')
if config_file and status:
        config_parser.read(config_file)
        # Depending on if dev or production, pull from a different section
        if status in config_parser.sections():
                environment = status
        else:
                raise InvalidEnvironment('Need to choose one of the options for your environment: %s' % ','.join(config_parser.sections()))
else:
        raise MissingApplicationConfig('Need to put a config ini file in your environment variables')

User.objects.filter(email='cccb@mail.dfci.harvard.edu').delete()
User.objects.create_superuser(config_parser.get(environment, 'superuser'), 'cccb@mail.dfci.harvard.edu', config_parser.get(environment, 'superuser_pwd'))
