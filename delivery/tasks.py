from celery.task.schedules import crontab
from celery.decorators import periodic_task
import email_utils
from models import *

import datetime
import os
import pandas as pd

from django.conf import settings

def bucket_list_html(sdf):
	bucket_listing_html = ''
	for bucket, bucket_level_df in sdf.groupby('bucket'):
		bucket_listing_template = "<ul><li>%s</li>%s</ul>"
		resource_list = ""
		for i,row in bucket_level_df.iterrows():
			resource_name = row['basename']
			resource_list += "<li>%s</li>" % resource_name
		resource_ul = '<ul>%s</ul>' % resource_list
		bucket_listing_html += bucket_listing_template % (bucket[len(settings.BUCKET_PREFIX):],resource_ul)
	return bucket_listing_html

@periodic_task(
	run_every=(crontab(minute=0, hour=0)),
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

	cccb_owners = [x.lower() for x in settings.CCCB_EMAIL_CSV.split(',')]

	expired_resources = []

	df = pd.DataFrame()
	for r in all_resources:
		days_up = (now-r.upload_date).days
		days_left = settings.RETENTION_PERIOD - days_up
		if days_left <= -1:
			expired_resources.append(r)
		bucket = r.bucket
		for owner in bucket.owners.all():
			if not owner.email.lower() in cccb_owners:  
				df = df.append( \
				{ \
					'user':owner.email, \
					'basename': r.basename, \
					'days_left': days_left, \
					'bucket': bucket.name, \
				}, \
				ignore_index=True)
			else:
				print 'skipping since %s was a CCCB email' % owner.email

	email_template = '<html><body>%s</body></html>'
	alert_days = settings.ALERT_DAYS
	for user, user_df in df.groupby('user'):
		for day, sdf in user_df.groupby('days_left'):
			if int(day) in alert_days:
				removal_date = now+datetime.timedelta(days=day)
				email_subject = '[CCCB] Data removal reminder'
				email_text = """
					<p>This is a reminder that the following files will be automatically removed 
					and deleted in %d days (on %s).  Please ensure you have downloaded and saved them.</p>
					<p><a href="%s">Go to site</a></p>
				""" % (day, removal_date.strftime('%B %d, %Y'), settings.HOST)
				listing_html = bucket_list_html(sdf)
				email_text += listing_html
				email_body = email_template % email_text
				print 'Send email to %s:%s' % (user, email_body)
				#TODO actually send email!
			elif int(day) <= -1:
				# set inactive on Resource, notify of deletion
				email_subject = '[CCCB] Data removal notification'
				email_text = "This is a notification that the following files have been removed from our data storage system."
				listing_html = bucket_list_html(sdf)
				email_text += listing_html
				email_body = email_template % email_text
				print 'Send email to %s:%s' % (user, email_body)
				#TODO actually send email!

	# create a set of commands to do removal:
	gsutil_rm_cmd_template = 'gsutil rm %s #%s;uploaded %s'
	removal_commands = []
	for r in expired_resources:
		non_cccb_owners = [x.email for x in r.bucket.owners.all() if not x.email.lower() in cccb_owners]
		non_cccb_owner_str = ','.join(non_cccb_owners)
		l = settings.GOOGLE_BUCKET_PREFIX + r.public_link[len(settings.PUBLIC_STORAGE_ROOT):]
		removal_commands.append(gsutil_rm_cmd_template % (l, non_cccb_owner_str, r.upload_date.strftime('%B %d, %Y')))

	email_utils.send_email(
		settings.GMAIL_CREDENTIALS, \
		'\n'.join(removal_commands), \
		 ['brian_lawney@mail.dfci.harvard.edu', ], \
		'[CCCBSEQ] Cleanup' \
	)
