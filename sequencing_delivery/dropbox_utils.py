# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import urllib
import httplib2
import json
import hashlib
import os

import sys
sys.path.append(os.path.abspath('..'))
import email_utils
sys.path.append(os.path.abspath('../delivery'))
from delivery.models import Bucket, Resource, DropboxTransferMaster, DropboxFileTransfer, ResourceDownload

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

from delivery import tasks

@login_required
def register_files_to_transfer(request):
	"""
        This accepts a ajax call which holds the information about the files to transfer
        This is because the auth flow with dropbox keeps us from directly transferring the data
	"""
	data = json.loads(request.POST.get('data'))
	request.session['files_to_transfer'] = data
	return HttpResponse('')

def dropbox_auth(request):
	print request.session
	token_request_uri = settings.DROPBOX_AUTH_ENDPOINT
        response_type = "code"
        # for validating that we're not being spoofed
        state = hashlib.sha256(os.urandom(1024)).hexdigest()
        request.session['session_state'] = state
        url = "{token_request_uri}?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}&force_reauthentication=true&state={state}".format(
        token_request_uri = token_request_uri,
        response_type = response_type,
        client_id = settings.DROPBOX_KEY,
        redirect_uri = settings.DROPBOX_REGISTERED_CALLBACK,
        state = state)
        print 'made url: %s' % url
        print '*'*200
        return HttpResponseRedirect(url)


def setup_destination_folder(client, bucket_name):
	cccb_download_folder = '/' + settings.DROPBOX_DEFAULT_DOWNLOAD_FOLDER
	ilab_project_id = bucket_name[len(settings.BUCKET_PREFIX):]
	destination_folder = os.path.join(cccb_download_folder, ilab_project_id)
	try:
		files = client.files_list_folder(destination_folder)
	except dropbox.exceptions.ApiError as ex:
		client.files_create_folder(destination_folder, autorename=True)
	return destination_folder


def dropbox_callback(request):
	print 'Dropbox request received: %s' % request.GET
	parser = httplib2.Http()
	if 'error' in request.GET or 'code' not in request.GET:
		print 'was error'
		return HttpResponseRedirect(reverse('unauthorized'))
	if request.GET['state'] != request.session['session_state']:
		return HttpResponseRedirect(reverse('unauthorized')) 
	
	params = urllib.urlencode({
        	'code':request.GET['code'],
        	'redirect_uri':settings.DROPBOX_REGISTERED_CALLBACK,
   	     'client_id':settings.DROPBOX_KEY,
        	'client_secret':settings.DROPBOX_SECRET,
        	'grant_type':'authorization_code'
	})
	
	code = request.GET['code']
	headers={'content-type':'application/x-www-form-urlencoded'}
	resp, content = parser.request(settings.DROPBOX_TOKEN_ENDPOINT, method = 'POST', body = params, headers = headers)
	c = json.loads(content)
	token = c['access_token']
	print 'DROPBOX_TOKEN=%s' % token
	ft = request.session.get('files_to_transfer', None)

	# get any existing transfers by this user:
	existing_transfer_masters = DropboxTransferMaster.objects.filter(owner=request.user)
	ongoing_transfers = []
	for t in existing_transfer_masters:
		ongoing_transfers.extend([x.source for x in DropboxFileTransfer.objects.filter(master=t)])

	transferred_file_list = []
	untransferred_file_list = []
	previously_completed_transfer_file_list = []
	ongoing_transfer_list = []

	if ft:
		master = DropboxTransferMaster(start_time = datetime.datetime.now(), owner = request.user)
		master.save()
		compute_client = discovery.build('compute', 'v1')
		storage_client = storage.Client()
		# get the current usage of the user's dropbox:
		dbx = dropbox.dropbox.Dropbox(token)
		space_usage = dbx.users_get_space_usage()
		if space_usage.allocation.is_team():
			used_in_bytes = space_usage.allocation.get_team().used
			space_allocation_in_bytes = space_usage.allocation.get_team().allocated
			space_remaining_in_bytes = space_allocation_in_bytes - used_in_bytes
			
		else:
			used_in_bytes = space_usage.used
			space_allocation_in_bytes = space_usage.allocation.get_individual().allocated
			space_remaining_in_bytes = space_allocation_in_bytes - used_in_bytes
		running_total = 0
		at_least_one_transfer = False
		transfer_dict = {}
		for i,f in enumerate(ft):
			# we can block the user from requesting downloads via the UI, but if that is stale, we need
			# to check on the backend.  Need to check that the file has not already been transferred, AND that 
			# it's not currently going.  A double-click seems very likely 

			# check that not already downloaded
			completed_resource_downloads = ResourceDownload.objects.filter(downloader=request.user)
			completed_download_urls = [x.resource.public_link for x in completed_resource_downloads]
			if f in completed_download_urls:
				print 'was already completed'
				print completed_download_urls
				previously_completed_transfer_file_list.append(f)
				continue

			# check that not ongoing:
			if f in ongoing_transfers:
				print 'is ongoing'
				ongoing_transfer_list.append(f)
				continue

			filepath = f[len(settings.PUBLIC_STORAGE_ROOT):]
			bucket_name = filepath.split('/')[0]
			object_path = '/'.join(filepath.split('/')[1:])
			bucket = storage_client.get_bucket(bucket_name)
			b = bucket.get_blob(object_path)
			size_in_bytes = b.size
			running_total += size_in_bytes
			if running_total < space_remaining_in_bytes:
				at_least_one_transfer = True
				destination = setup_destination_folder(dbx, bucket_name)
				transfer_dict[f] = (destination, size_in_bytes)
				transferred_file_list.append(f)
			else:
				untransferred_file_list.append(f)
		# in case we do not actually transfer any files, don't want the 'master' objects sticking around in the database
		if not at_least_one_transfer:
			master.delete()
		if len(transfer_dict.keys()) > 0:
			tasks.start_transfers.delay(transfer_dict, master.pk, token)

	else:
		transferred_file_list = []
		untransferred_file_list = []
	return render(request, 'delivery/dropbox_transfer.html', {'transferred_files':transferred_file_list, \
                                                                  'skipped_files':untransferred_file_list, \
                                                                  'previously_completed_transfer_file_list':previously_completed_transfer_file_list, \
                                                                   'ongoing_transfer_list':ongoing_transfer_list})


@csrf_exempt
def dropbox_transfer_complete(request):
	print 'received request from dropbox worker completion'
	print request.POST
	if 'token' in request.POST:
		b64_enc_token = request.POST['token']
		enc_token = base64.decodestring(b64_enc_token)
		expected_token = settings.TOKEN
		obj=DES.new(settings.ENCRYPTION_KEY, DES.MODE_ECB)
		decrypted_token = obj.decrypt(enc_token)
		if decrypted_token == expected_token:
			print 'token matched'
			master_pk = int(request.POST.get('masterPK', ''))
			transfer_pk = int(request.POST.get('transferPK', ''))
			transfer_error = int(request.POST.get('error', 0))
			print 'go look for master_pk=%d, transfer_pk=%d' % (master_pk, transfer_pk)
			try:
				master = DropboxTransferMaster.objects.get(pk = master_pk)
				transfer = DropboxFileTransfer.objects.get(pk=transfer_pk)
				transfer.is_complete = True
				if transfer_error == 1:
					transfer.was_success = False
				else:
					transfer.was_success = True

					# register that file has been transferred to block multiple downloads
					source = transfer.source # the https link
					resource_list = Resource.objects.filter(public_link=source)
					if len(resource_list) == 1:
						rd = ResourceDownload(resource=resource_list[0], downloader=master.owner, download_date=datetime.datetime.now())
						rd.save()
					else:
						print 'Problem!  Got a resource list that was not of length=1.'
						print resource_list

				transfer.save()

				all_transfers = master.dropboxfiletransfer_set.all()
				if all([x.is_complete for x in all_transfers]) and master.initiated_all_transfers:

					# all transfers done, but not all were necessarily successful.
					if all([x.was_success for x in all_transfers]):
						print 'delete transfer master'
						li_string = ''.join(['<li>%s</li>' % os.path.basename(x.source) for x in all_transfers])
						msg = "<html><body>Your file transfer to Dropbox has completed!  The following files should now be in your Dropbox:<ul>%s</ul></body></html>" % li_string
						# note that the email has to be nested in a list
						email_subject = '[CCCB] Dropbox transfer complete'
						print 'will send msg: %s\n to: %s' % (msg,master.owner.email)
					else: # some failed
						successful_transfers = [x for x in all_transfers if x.was_success]
						failed_transfers = [x for x in all_transfers if not x.was_success]
						success_li_string = ''.join(['<li>%s</li>' % os.path.basename(x.source) for x in successful_transfers])
						failed_li_string = ''.join(['<li>%s</li>' % os.path.basename(x.source) for x in failed_transfers])
						msg = """<html>
							<body>Your file transfer to Dropbox has experienced an issue."""
						if len(successful_transfers) > 0:
							msg += """The following files were successfully transferred and should now be in your Dropbox:
								<ul>%s</ul>""" % success_li_string
						if len(failed_transfers) > 0:
							msg += """The following transfers failed and should be restarted.  
								Sometimes an unexpected error occurs in the connection with Dropbox and it is best to refresh and try again.  The CCCB has also received an error message
								regarding the transfer(s).
								<ul>%s</ul>""" % failed_li_string
						# note that the email has to be nested in a list
						msg += "</body></html>"
						print 'will send msg: %s\n to: %s' % (msg,master.owner.email)
						email_subject = '[CCCB] Problem with Dropbox transfer'
					email_utils.send_email(os.path.join(settings.BASE_DIR, settings.GMAIL_CREDENTIALS), msg, [master.owner.email,], email_subject)
					master.delete()
				else:
					print 'wait for other transfers to complete or to even begin'
				return HttpResponse('Acknowledged.')
			except Exception as ex:
				print 'caught some exception: %s' % ex.message
				return HttpResponseBadRequest('')
		else:
			print 'token did not match'
			return HttpResponseBadRequest('')
	else:
		print 'token NOT in request'
		return HttpResponseBadRequest('')
