from __future__ import unicode_literals
import time
import datetime
import urllib
import httplib2
import json
import hashlib
import os
import sys
sys.path.append(os.path.abspath('..'))

from google.cloud import storage
import googleapiclient.discovery as discovery

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.conf import settings
from django.urls import reverse
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from Crypto.Cipher import DES
import base64

import dropbox 
from dropbox import DropboxOAuth2FlowNoRedirect

from celery.task.schedules import crontab
from celery.decorators import task, periodic_task
import email_utils
from models import *

import pandas as pd


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
				email_utils.send_email(settings.GMAIL_CREDENTIALS, email_body, [user,], email_subject)
			elif int(day) <= -1:
				# set inactive on Resource, notify of deletion
				email_subject = '[CCCB] Data removal notification'
				email_text = "This is a notification that the following files have been removed from our data storage system."
				listing_html = bucket_list_html(sdf)
				email_text += listing_html
				email_body = email_template % email_text
				email_utils.send_email(settings.GMAIL_CREDENTIALS, email_body, [user,], email_subject)

	# create a set of commands to do removal:
	gsutil_rm_cmd_template = 'gsutil rm %s #%s;uploaded %s'
	removal_commands = []
	for r in expired_resources:
		r.is_active = False
		r.save()
		non_cccb_owners = [x.email for x in r.bucket.owners.all() if not x.email.lower() in cccb_owners]
		non_cccb_owner_str = ','.join(non_cccb_owners)
		l = settings.GOOGLE_BUCKET_PREFIX + r.public_link[len(settings.PUBLIC_STORAGE_ROOT):]
		removal_commands.append(gsutil_rm_cmd_template % (l, non_cccb_owner_str, r.upload_date.strftime('%B %d, %Y')))

	email_utils.send_email(
		settings.GMAIL_CREDENTIALS, \
		'\n'.join(removal_commands), \
		 [settings.CCCB_GROUP_EMAIL, ], \
		'[CCCBSEQ] Cleanup' \
	)


@task(name='start_transfers')
def start_transfers(transfer_dict, master_pk, token):
	"""
	transfer_dict is a dictionary where the key is the source of the transfer (a link to a google bucket object)
	and that maps to a tuple of the destination folder (in dropbox) and the size in bytes (so we know how big to make
	the temporary VM's disk).

	master_pk is an integer which is the primary key for the 'transfer master'
	token is a string which is the dropbox oauth2 token    
	"""

	compute_client = discovery.build('compute', 'v1')

	master_obj = DropboxTransferMaster.objects.get(pk=master_pk)
	source_links = transfer_dict.keys()

	transfer_idx = 0
	while len(source_links) > 0:

		# get the current number of transfers:
		all_existing_transfers = master_obj.dropboxfiletransfer_set.all()
		completed_transfers = sum([x.is_complete for x in all_existing_transfers])
		currently_processing_transfers = len(all_existing_transfers) - completed_transfers

		if currently_processing_transfers < settings.MAX_CONCURRENT_TRANSFERS:
			source_link = source_links.pop()	
			dropbox_destination_folderpath, size_in_bytes = transfer_dict[source_link]
			transfer = DropboxFileTransfer(source=source_link, start_time = datetime.datetime.now(), master=master_obj)
			transfer.save()
			do_transfer(source_link, dropbox_destination_folderpath, transfer_idx, master_pk, transfer, token, compute_client, size_in_bytes)
			transfer_idx += 1
		else:
			# the current number of transfers is at the max, so wait a bit
			time.sleep(settings.DROPBOX_TRANSFER_SLEEP_SECONDS)

	# set a flag to state that all the transfers have at least been started
	# This flag will prevent completed transfers from deleting the master_obj.
	# Avoids a race condition.
	master_obj.initiated_all_transfers = True
	master_obj.save()

 
def do_transfer(file_source, dropbox_destination_folderpath, transfer_idx, master_pk, transfer, token, compute_client, size_in_bytes):
	"""
	file_source is the https:// link to the file
	transfer_idx is an integer.  This helps isn potentially avoiding conflicts with the time-stamped machine names
	master_pk is the primary key of a DropboxTransferMaster object
	token is a auth token for dropbox
	"""
	#storage_client = storage.Client()
	prefix = settings.PUBLIC_STORAGE_ROOT
	file_path = file_source[len(prefix):]
	size_in_gb = size_in_bytes/1e9
	min_size = settings.DROPBOX_TRANSFER_MIN_DISK_SIZE
	buffer = 5
	config_params = {}
	config_params['google_project'] = settings.GOOGLE_PROJECT
	config_params['image_name'] = settings.DROPBOX_TRANSFER_IMAGE
	config_params['transfer_idx'] = transfer_idx
	config_params['disk_size_in_gb'] = min_size if (size_in_gb + buffer) <= min_size else int(buffer + size_in_gb)
	config_params['default_zone'] = settings.GOOGLE_DEFAULT_ZONE
	config_params['machine_type'] = 'g1-small'
	config_params['gs_prefix'] = settings.GOOGLE_BUCKET_PREFIX
	config_params['startup_bucket'] = settings.STARTUP_SCRIPT_BUCKET
	config_params['startup_script'] = 'dropbox_startup_script.py'
	config_params['callback_url'] = '%s/%s' % (settings.HOST, settings.DROPBOX_COMPLETE_CALLBACK)
	config_params['master_pk'] = master_pk
	config_params['transfer_pk'] = transfer.pk
	config_params['file_source'] = file_path
	config_params['dropbox_token'] = token
	config_params['email_utils'] = settings.EMAIL_UTILS
	config_params['email_credentials'] = settings.GMAIL_CREDENTIALS_CLOUD
	config_params['dropbox_destination_folderpath'] = dropbox_destination_folderpath
	print 'launch instance with params: %s' % config_params
	launch_custom_instance(compute_client, config_params)


def launch_custom_instance(compute, config_params):

    now = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    instance_name = 'dropbox-transfer-%s-%s' % (now, config_params['transfer_idx'])

    source_disk_image = config_params['image_name']
    disk_size_in_gb = config_params['disk_size_in_gb']
    machine_type = "zones/%s/machineTypes/%s" % (config_params['default_zone'], config_params['machine_type'])
    startup_script_url = config_params['gs_prefix'] + os.path.join(config_params['startup_bucket'], config_params['startup_script']) 
    callback_url = config_params['callback_url']
    master_pk = config_params['master_pk']
    transfer_pk = config_params['transfer_pk']
    file_source = config_params['file_source']
    dropbox_token = config_params['dropbox_token']
    dropbox_destination_folderpath = config_params['dropbox_destination_folderpath']
    token = settings.TOKEN
    enc_key = settings.ENCRYPTION_KEY
    email_utils = os.path.join(config_params['startup_bucket'], config_params['email_utils'])
    email_credentials = config_params['email_credentials']

    config = {
        'name': instance_name,
        'machineType': machine_type,

        # Specify the boot disk and the image to use as a source.
        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': source_disk_image,
                     "diskSizeGb": disk_size_in_gb,
                }
            }
        ],

        # Specify a network interface with NAT to access the public
        # internet.
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [
                {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
            ]
        }],

        # Allow the instance to access cloud storage and logging.
        'serviceAccounts': [{
            'email': 'default',
            'scopes': [
                'https://www.googleapis.com/auth/compute',
                'https://www.googleapis.com/auth/devstorage.full_control',
                'https://www.googleapis.com/auth/logging.write'
            ]
        }],
 
        'metadata': {
            'items': [{
                # Startup script is automatically executed by the
                # instance upon startup.
                'key': 'startup-script-url',
                'value': startup_script_url
            },
            {
              'key':'master_pk',
              'value': master_pk
            },
            {
              'key':'transfer_pk',
              'value': transfer_pk
            },
            {
                'key':'callback_url',
                'value': callback_url
            },
            {
              'key':'dropbox_token',
              'value':dropbox_token
            },
            {
              'key':'source',
              'value':file_source
            },
	    {
              'key':'token', 
              'value':token
            },
	    {
              'key':'enc_key', 
              'value':enc_key
            },
            {
              'key':'google_project',
              'value': config_params['google_project']
            },
            {
              'key':'google_zone',
              'value': config_params['default_zone']
            },
            {
              'key':'cccb_email_csv',
              'value': settings.CCCB_EMAIL_CSV
            },
            {
              'key':'email_utils',
              'value': email_utils
            },
            {
              'key':'email_credentials',
              'value': email_credentials
            },
            {
              'key':'dropbox_destination_folderpath',
              'value': dropbox_destination_folderpath
            },
          ]
        }
    }
    return compute.instances().insert(
        project=config_params['google_project'],
        zone=config_params['default_zone'],
        body=config).execute()
