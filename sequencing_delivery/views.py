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
from delivery.models import Bucket, Resource, ResourceType, DropboxTransferMaster, DropboxFileTransfer

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

def default_home(request):
    return redirect('login')


def unauthorized(request):
    return HttpResponse('This user has not been authorized by the CCCB', status=403)


def login(request):
    return render(request, 'account/login.html', {})


def google_login(request):
    """
    Starts the auth flow with google
    """
    token_request_uri = settings.GOOGLE_AUTH_ENDPOINT
    response_type = "code"
    # for validating that we're not being spoofed
    state = hashlib.sha256(os.urandom(1024)).hexdigest()
    request.session['session_state'] = state
    url = "{token_request_uri}?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}".format(
    token_request_uri = token_request_uri,
    response_type = response_type,
    client_id = settings.GOOGLE_CLIENT_ID,
    redirect_uri = settings.GOOGLE_REGISTERED_CALLBACK,
    scope = settings.AUTH_SCOPE,
    state = state)
    return HttpResponseRedirect(url)


def oauth2_callback(request):
    """
    This is the view that Google calls back as part of the OAuth2 flow
    """
    parser = httplib2.Http()
    if 'error' in request.GET or 'code' not in request.GET:
        return HttpResponseRedirect(reverse('unauthorized'))
    if request.GET['state'] != request.session['session_state']:
        return HttpResponseRedirect(reverse('unauthorized')) 
    params = urllib.urlencode({
                'code':request.GET['code'],
                'redirect_uri':settings.GOOGLE_REGISTERED_CALLBACK,
                'client_id':settings.GOOGLE_CLIENT_ID,
                'client_secret':settings.GOOGLE_CLIENT_SECRET,
                'grant_type':'authorization_code'
    })
    headers={'content-type':'application/x-www-form-urlencoded'}
    resp, content = parser.request(settings.ACCESS_TOKEN_URI, method = 'POST', body = params, headers = headers)
    c = json.loads(content)
    token_data = c['access_token']
    token_uri = '%s?access_token=%s' % (settings.USER_INFO_URI, token_data)
    resp, content = parser.request(token_uri)
    content = json.loads(content)
    print content
    is_verified = content['verified_email']
    email = content['email']
    if is_verified:
        # find projects
        print 'Got email %s' % email
        try:
            user = User.objects.get(email=email)
        except ObjectDoesNotExist as ex:
            user = User.objects.create_user(email, email, settings.DEFAULT_PWD)
            user.first_name = ''
            user.last_name = ''
            user.save()
        django_login(request, user)
        return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    else:
        return redirect('unauthorized')

@csrf_exempt
def update_db(request):
	import ast
	user_ip = request.META['REMOTE_ADDR']
	print 'x'*20
	print request.POST
	print 'x'*20
	b64_enc_token = request.POST['token']
	enc_token = base64.decodestring(b64_enc_token)
	expected_token = settings.TOKEN
	obj=DES.new(settings.ENCRYPTION_KEY, DES.MODE_ECB)
	decrypted_token = obj.decrypt(enc_token)
	if decrypted_token == expected_token:

		print 'token looks good'
		all_resource_types = ResourceType.objects.all()


		uploads = request.POST['uploads']
		ddd = json.loads(uploads)
		#dd = ast.literal_eval(uploads)
		print 'Y'*100
		print ddd
		print 'Y'*100
		for item in ddd['uploaded_objects']:
			for email in item['owners']:
				try:
					user = User.objects.get(email=email)
				except User.DoesNotExist:
					user = User.objects.create_user(email, email, settings.DEFAULT_PWD)
					user.first_name = ''
					user.last_name = ''
					user.save()

				# see if the bucket exists:
				try:
					bucket = Bucket.objects.get(name=item['bucket_name'])
				except ObjectDoesNotExist:
					bucket = Bucket(name=item['bucket_name'])
					bucket.save()
				bucket.owners.add(user)
				public_link = settings.LINK_ROOT % (bucket.name,item['basename'])

				# determine the type of file by the suffix
				this_resource_type = None
				for rt in all_resource_types:
					if item['basename'][-len(rt.filename_suffix):] == rt.filename_suffix:
						this_resource_type = rt
						break
				if this_resource_type is None:
					print 'resource type was none'
					print item
					return HttpResponse('', status=404)
				try:
					# if it exists already we update the upload date
					resource = Resource.objects.get(bucket = bucket, basename = item['basename'])
					resource.upload_date = datetime.datetime.now()
					resource.save()
				except ObjectDoesNotExist:
					resource = Resource(basename=item['basename'],
							bucket = bucket,
							public_link = public_link,
							resource_type = this_resource_type,
							upload_date = datetime.datetime.now())
					resource.save()
		return HttpResponse('Database updated.')
	else:
		return HttpResponse('', status=403)


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
	#ft = ['https://storage.cloud.google.com/cccb-app-service-2-062217-192238/uploads/YX22_R1.fastq.gz', 'https://storage.cloud.google.com/cccb-app-service-2-062217-192238/uploads/YX23_R1.fastq.gz', 'https://storage.cloud.google.com/cccb-app-service-2-062217-192238/uploads/YX23_R2.fastq.gz']
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
		transferred_file_list = []
		untransferred_file_list = []
		at_least_one_transfer = False
		for i,f in enumerate(ft):
			filepath = f[len(settings.PUBLIC_STORAGE_ROOT):]
			bucket_name = filepath.split('/')[0]
			object_path = '/'.join(filepath.split('/')[1:])
			bucket = storage_client.get_bucket(bucket_name)
			b = bucket.get_blob(object_path)
			size_in_bytes = b.size
			running_total += size_in_bytes
			if running_total < space_remaining_in_bytes:
				at_least_one_transfer = True
				t = DropboxFileTransfer(source=f, start_time = datetime.datetime.now(), master=master)
				t.save()
				do_transfer(f, i, master, t, token, compute_client, size_in_bytes)
				transferred_file_list.append(f)
			else:
				untransferred_file_list.append(f)
		# in case we do not actually transfer any files, don't want the 'master' objects sticking around in the database
		if not at_least_one_transfer:
			master.delete() 
	else:
		transferred_file_list = []
		untransferred_file_list = []
	return render(request, 'delivery/dropbox_transfer.html', {'transferred_files':transferred_file_list, 'skipped_files':untransferred_file_list})


def do_transfer(file_source, transfer_idx, master, transfer, token, compute_client, size_in_bytes):
	"""
	file_source is the https:// link to the file
	transfer_idx is an integer.  This helps isn potentially avoiding conflicts with the time-stamped machine names
	master is a DropboxTransferMaster object
	token is a auth token for dropbox
	"""
	#storage_client = storage.Client()
	prefix = settings.PUBLIC_STORAGE_ROOT
	file_path = file_source[len(prefix):]
	#bucket_name = file_path.split('/')[0]
	#object_path = '/'.join(file_path.split('/')[1:])
	#print bucket_name
	#bucket = storage_client.get_bucket(bucket_name)
	#b = bucket.get_blob(object_path)
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
	config_params['master_pk'] = master.pk
	config_params['transfer_pk'] = transfer.pk
	config_params['file_source'] = file_path
	config_params['dropbox_token'] = token
	config_params['email_utils'] = settings.EMAIL_UTILS
	config_params['email_credentials'] = settings.GMAIL_CREDENTIALS
	print 'launch instance with params: %s' % config_params
	launch_custom_instance(compute_client, config_params)


@login_required
def register_files_to_transfer(request):
	"""
	This accepts a ajax call which holds the information about the files to transfer
	This is because the auth flow with dropbox keeps us from directly transferring the data
	"""
	data = json.loads(request.POST.get('data'))
	request.session['files_to_transfer'] = data
	return HttpResponse('')


def launch_custom_instance(compute, config_params):

    now = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    instance_name = 'dropbox-transfer-%s-%s' % (now, config_params['transfer_idx'])

    source_disk_image = 'projects/%s/global/images/%s' % (config_params['google_project'], config_params['image_name'])
    disk_size_in_gb = config_params['disk_size_in_gb']
    machine_type = "zones/%s/machineTypes/%s" % (config_params['default_zone'], config_params['machine_type'])
    startup_script_url = config_params['gs_prefix'] + os.path.join(config_params['startup_bucket'], config_params['startup_script']) 
    callback_url = config_params['callback_url']
    master_pk = config_params['master_pk']
    transfer_pk = config_params['transfer_pk']
    file_source = config_params['file_source']
    dropbox_token = config_params['dropbox_token']
    token = settings.TOKEN
    enc_key = settings.ENCRYPTION_KEY
    email_utils = os.path.join(config_params['startup_bucket'], config_params['email_utils'])
    email_credentials = os.path.join(config_params['startup_bucket'], config_params['email_credentials'])

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
          ]
        }
    }
    return compute.instances().insert(
        project=config_params['google_project'],
        zone=config_params['default_zone'],
        body=config).execute()


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
			try:
				transfer = DropboxFileTransfer.objects.get(pk=transfer_pk)
				transfer.is_complete = True
				transfer.save()
				master = DropboxTransferMaster.objects.get(pk = master_pk)
				all_transfers = master.dropboxfiletransfer_set.all()
				if all([x.is_complete for x in all_transfers]):
					print 'delete transfer master'
					li_string = ''.join(['<li>%s</li>' % os.path.basename(x.source) for x in all_transfers])
					msg = "<html><body>Your file transfer to Dropbox has completed!  The following files should now be in your Dropbox:<ul>%s</ul></body></html>" % li_string
					# note that the email has to be nested in a list
					print 'will send msg: %s\n to: %s' % (msg,master.owner.email)
					email_utils.send_email(os.path.join(settings.BASE_DIR, settings.GMAIL_CREDENTIALS), msg, [master.owner.email,], '[CCCB] Dropbox transfer complete')
					master.delete()
				else:
					print 'wait for other transfers to complete'
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
