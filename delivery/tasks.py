from celery.task.schedules import crontab
from celery.decorators import periodic_task
import email_utils
from models import *

import datetime

from django.conf import settings

@periodic_task(
	run_every=(crontab()),
	name='cleanup'
)
def cleanup():
	print 'In cleanup'

	# query db for all resources:
	all_resources = Resource.objects.all()

	# to do a 'date subtraction' below, need the time zone info for the dates in the database
	# extract that from the first resource returned for ease.  
	tz_info = all_resources[0].upload_date.tzinfo
	now = datetime.datetime.now(tz_info)

	# get those that are expired:
	expired_resources = [x for x in all_resources if (now-x.upload_date).days >= settings.RETENTION_PERIOD]
	
	# get the buckets associated with those expired resources:
	bucket_to_resource_map = {}
	for r in expired_resources:
		if r.bucket in bucket_to_resource_map:
			bucket_to_resource_map[r.bucket].append(r)
		else:
			bucket_to_resource_map[r.bucket] = [r,]

	# get the owners of those buckets:
	bucket_set = bucket_to_resource_map.keys()
	owner_to_bucket_mapping = {}
	for b in bucket_set:
		for owner in b.owners.all():
			if owner.email in owner_to_bucket_mapping:
				owner_to_bucket_mapping[owner.email].append(b)
			else:
				owner_to_bucket_mapping[owner.email] = [b,]

	for o, bucket_list in owner_to_bucket_mapping.items():
		print 'Owner: %s\n' % o
		for b in bucket_list:
			print '\tBucket: %s\n' % b.name
			for resource in bucket_to_resource_map[b]:
				print '\t\t%s (uploaded %s)\n' % (resource.basename, resource.upload_date.strftime('%B %d, %Y'))

	email_utils.send_email(
		settings.GMAIL_CREDENTIALS, \
		"Here is a test email from the cront job", \
		 ['brianlawney@gmail.com', 'brian_lawney@mail.dfci.harvard.edu'], \
		'[CCCB] cron generated message' \
	)
