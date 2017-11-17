from celery.task.schedules import crontab
from celery.decorators import periodic_task
import email_utils

from django.conf import settings

@periodic_task(
	run_every=(crontab()),
	name='cleanup'
)
def cleanup():
	print 'In cleanup'
	email_utils.send_email(
		settings.GMAIL_CREDENTIALS, \
		"Here is a test email from the cront job", \
		 ['brianlawney@gmail.com', 'brian_lawney@mail.dfci.harvard.edu'], \
		'[CCCB] cron generated message' \
	)
