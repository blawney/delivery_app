"""
Django settings for sequencing_delivery project.

Generated by 'django-admin startproject' using Django 1.11.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os


class MissingApplicationConfig(Exception):
	pass

class InvalidEnvironment(Exception):
	pass


# read config options:
from ConfigParser import SafeConfigParser
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

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config_parser.get(environment, 'django_secret', raw=True)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config_parser.getboolean(environment, 'debug')

ALLOWED_HOSTS = [config_parser.get(environment, 'instance_ip'), config_parser.get(environment, 'domain')]


# Application definition

INSTALLED_APPS = [
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'delivery',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sequencing_delivery.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'),],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sequencing_delivery.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': '/cloudsql/%s:%s:%s' % (config_parser.get(environment, 'google_project'), \
                                        config_parser.get(environment, 'google_default_region'), \
                                        config_parser.get(environment, 'cloud_sql_db')),
        'NAME': config_parser.get(environment, 'db_name'),
        'USER': config_parser.get(environment, 'db_user'),
        'PASSWORD': config_parser.get(environment, 'db_password')
    }
}

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/explorer/'
SITE_ID = 1

# the base of our address:
HOST = '%s://%s' % (config_parser.get(environment, 'protocol'), config_parser.get(environment, 'domain'))

# the name of the directory where we hold the credentials:
CREDENTIAL_DIR = os.path.join(BASE_DIR, 'credentials')

STORAGE_API_URI = 'https://storage.googleapis.com'

# some settings related to authenticating with google:
GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_CLIENT_ID = config_parser.get(environment, 'oauth2_client')
GOOGLE_CLIENT_SECRET = config_parser.get(environment, 'oauth2_secret', raw=True)
GOOGLE_REGISTERED_CALLBACK = os.path.join(HOST, 'callback/')
AUTH_SCOPE = 'https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email'
ACCESS_TOKEN_URI = 'https://accounts.google.com/o/oauth2/token'
USER_INFO_URI = 'https://www.googleapis.com/oauth2/v1/userinfo'


# doesn't really matter since users are not logging themselves in anyway
DEFAULT_PWD = 'ARvadf8adBadjh!#dfdf'


# when creating a link, link to the public api point for google storage
LINK_ROOT = 'https://storage.cloud.google.com/%s/%s'

BUCKET_PREFIX = 'cccb-seq-main-'

# for providing a basic auth when the CCCB servers upload files and need to update the db
# just want to keep out random requests
# for communicating between VMs internally, we use keys to avoid junk requests
TOKEN = config_parser.get(environment, 'comm_token', raw=True)
ENCRYPTION_KEY = config_parser.get(environment, 'encryption_key', raw=True)

#dropbox parameters:
DROPBOX_AUTH_ENDPOINT = 'https://www.dropbox.com/oauth2/authorize'
DROPBOX_TOKEN_ENDPOINT = 'https://api.dropboxapi.com/oauth2/token'
DROPBOX_REGISTERED_CALLBACK = HOST +'/dbx-callback'
DROPBOX_KEY=config_parser.get(environment, 'dropbox_key', raw=True)
DROPBOX_SECRET=config_parser.get(environment, 'dropbox_secret', raw=True)
DROPBOX_TRANSFER_IMAGE = 'projects/cccb-data-delivery/global/images/dropbox-transfer-image-v2' # the name of the google machine image
DROPBOX_TRANSFER_MIN_DISK_SIZE = 10
DROPBOX_COMPLETE_CALLBACK = 'dropbox-transfer-complete'
DROPBOX_DEFAULT_DOWNLOAD_FOLDER = 'cccb_transfers'

GOOGLE_PROJECT = config_parser.get(environment, 'google_project')
GOOGLE_DEFAULT_ZONE = config_parser.get(environment, 'google_default_zone')
GOOGLE_BUCKET_PREFIX = 'gs://'
PUBLIC_STORAGE_ROOT = 'https://storage.cloud.google.com/'
STARTUP_SCRIPT_BUCKET = config_parser.get(environment, 'startup_script_bucket')
GMAIL_CREDENTIALS_CLOUD = config_parser.get(environment, 'gmail_credentials_json')
gmail_cred_file = os.path.basename(GMAIL_CREDENTIALS_CLOUD)
GMAIL_CREDENTIALS = os.path.join(CREDENTIAL_DIR, gmail_cred_file)
EMAIL_UTILS = 'email_utils.py'
CCCB_EMAIL_CSV = config_parser.get(environment, 'cccb_email_csv') # emails to let CCCB staff know about problems:
CCCB_GROUP_EMAIL = config_parser.get(environment, 'cccb_group_email')

#Celery settings:
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'


