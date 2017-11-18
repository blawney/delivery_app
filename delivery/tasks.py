from celery.task.schedules import crontab
from celery.decorators import periodic_task
import email_utils
from models import *

import datetime
import os
import pandas as pd

from django.conf import settings

@periodic_task(
	run_every=(crontab()),
	name='cleanup'
)
def cleanup():
	print 'In cleanup'

	# query db for all resources:
	all_resources = Resource.objects.filter(is_active=True)

	# to do a 'date subtraction' below, need the time zone info for the dates in the database
	# extract that from the first resource returned for ease.  
	tz_info = all_resources[0].upload_date.tzinfo
	now = datetime.datetime.now(tz_info)

	# a list of how many days the resources have been there
	days_up = [(now-x.upload_date).days for x in all_resources]

	# days left until deletion.  Could be negative initially or if cleanup is not performed regularly/enforced
	days_left = [settings.RETENTION_PERIOD-x for x in days_up]

	cccb_owners = [x.lower() for x in settings.CCCB_EMAIL_CSV.split(',')]
	print cccb_owners

	df = pd.DataFrame()
	for r in all_resources:
		days_up = (now-r.upload_date).days
		days_left = settings.RETENTION_PERIOD - days_up
		bucket = r.bucket
		for owner in bucket.owners.all():
			if not owner.email.lower() in cccb_owners:  
				df = df.append( \
				{ \
					'user':owner.email, \
					'resource_pk': r.pk, \
					'days_left': days_left, \
					'bucket': bucket.name, \
				}, \
				ignore_index=True)
			else:
				print 'skipping since %s was a CCCB email' % owner.email

	df.to_csv(os.path.join(settings.BASE_DIR, 'expiration.tsv'), sep='\t')

	email_template = '<html><body>%s</body></html>'
	alert_days = settings.ALERT_DAYS
	for user, user_df in df.groupby('user'):
		for day, sdf in user_df.groupby('days_left'):
			if int(day) in alert_days:
				email_subject = '[CCCB] Data removal reminder'
				email_text = """
					This is a reminder that the following files will be automatically removed
					and deleted in %d days.  Please ensure you have downloaded and saved them.
				""" % day
				
				for bucket, bucket_level_df in sdf.groupby('bucket'):
					bucket_listing_template = "<ul><li>%s</li>%s</ul>"
					resource_list = ""
					for row in bucket_level_df.iterrows():
						# TODO get resource name that is meaningful using the pk in the dataframe
						resource_name = ''
						resource_list += "<li>%s</li>" % resource_name
					resource_ul = '<ul>%s</ul>' % resource_list
					bucket_listing_html = bucket_listing_template % (bucket,resource_ul)
			elif int(day) == -1:
				# set inactive on Resource, notify of deletion
				pass
			elif int(day) < -1:
				# if we have already expired items
				pass
	# get those that are expired:
	expired_resources = [x for x in all_resources if (now-x.upload_date).days >= settings.RETENTION_PERIOD]

	# get resources that will expire soon:
	#pending_resources = [x for x in all_resources if (now-x.upload_date).days >= settings.RETENTION_PERIOD]
	
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
