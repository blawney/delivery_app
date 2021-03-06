"""
This script is used for populating the development database with example data.
There should be files in a 'demo' bucket so it all is legit.
"""
import sys
import os
import json
import datetime

app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(app_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sequencing_delivery.settings')

import django
django.setup()
from django.conf import settings
from django.db.utils import IntegrityError
from delivery.models import Bucket, Resource
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from google.cloud import storage

# some constants:
email = 'brianlawney@gmail.com'
bucket_name = 'cccb-sequence-delivery-test-bucket'

# create a user
try:
	user = User.objects.get(email=email)
except User.DoesNotExist:
	user = User.objects.create_user(email, email, settings.DEFAULT_PWD)
	user.first_name = ''
	user.last_name = ''
	user.save()


bucket = Bucket.objects.get_or_create(name=bucket_name)[0]
print bucket
bucket.owners.add(user)
bucket.save()

# list the bucket to ensure that everything is consistent:
storage_client = storage.Client()
google_bucket = storage_client.get_bucket(bucket_name)
all_contents = google_bucket.list_blobs()
all_contents = [x for x in all_contents] # turns the iterator into a list so we can re-use

# just ensure we have read privileges for this hypothetical user:
for item in all_contents:
	acl = item.acl
	entity = acl.user(user.email)
	entity.grant_read()
	acl.save()

# normally we supply the Resource "title" when we update, so make some up here
resource_types = {
	'FastQ Sequence Files':'fastq.gz',\
	'FastQC Reports':'zip'
}
for item in all_contents:
	print 'Add resource: %s' % item.name
	public_link = settings.LINK_ROOT % (google_bucket.name, item.name)
	resource_title = ''
	for title, suffix in resource_types.items():
		if os.path.basename(item.name)[-len(suffix):] == suffix:
			resource_title = title
			break
	try:
		resource = Resource.objects.get(bucket = bucket, basename =os.path.basename(item.name))
		resource.resource_title = resource_title
		resource.upload_date = datetime.datetime.now()
	except ObjectDoesNotExist:
		resource = Resource(basename=os.path.basename(item.name), \
			bucket = bucket, \
			public_link = public_link, \
			resource_title = resource_title, \
			upload_date = datetime.datetime.now())
	resource.save()
