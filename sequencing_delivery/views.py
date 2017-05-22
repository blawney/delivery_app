# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import urllib
import httplib2
import json
import hashlib
import os

import sys
sys.path.append(os.path.abspath('../delivery'))
from delivery.models import Bucket, Resource, ResourceType

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from Crypto.Cipher import DES
import base64


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

	b64_enc_token = request.POST['token']
	enc_token = base64.decodestring(b64_enc_token)
	expected_token = settings.TOKEN
	obj=DES.new(settings.ENCRYPTION_KEY, DES.MODE_ECB)
	decrypted_token = obj.decrypt(enc_token)
	if decrypted_token == expected_token:

		all_resource_types = ResourceType.objects.all()


		uploads = request.POST['uploads']
		ddd = json.loads(uploads)
		#dd = ast.literal_eval(uploads)

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
					return HttpResponse('', status=404)
				try:
					# if it exists already we do nothing
					resource = Resource.objects.get(bucket = bucket, basename = item['basename'])
				except ObjectDoesNotExist:
					resource = Resource(basename=item['basename'],
							bucket = bucket,
							public_link = public_link,
							resource_type = this_resource_type,
							upload_date = datetime.datetime.now())
					resource.save()
		return HttpResponse('I hear you!\nYour IP was %s\n' % user_ip)
	else:
		return HttpResponse('', status=403)
