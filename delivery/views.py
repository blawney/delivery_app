# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import urllib
import httplib2
import json
import hashlib
import os
import collections

from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from models import Bucket, ResourceType, Resource, ResourceDownload

EXPIRED_LINK_MARKER = '#'

@login_required
def explorer(request):
    user = request.user
    resource_types = ResourceType.objects.all()
    #users_buckets = Bucket.objects.filter(owner=user)
    user_buckets = user.bucket_set.all()
    all_links = {}
    bucket_dates = [] # used for ordering in the UI
    for ub in user_buckets:
        bucket_name = ub.name[len(settings.BUCKET_PREFIX):].upper()
        d = {}
        the_date = None
        for rt in resource_types:
            resource_set = Resource.objects.filter(resource_type = rt, bucket = ub)
            if len(resource_set) > 0:
                last_upload_date = sorted([x.upload_date for x in resource_set])[-1]
                if the_date is None or last_upload_date > the_date:
                    date_string = last_upload_date.strftime('%B %d, %Y')
                    the_date = last_upload_date
                sorted_files_dict = collections.OrderedDict()
                for rr in sorted(resource_set, key=lambda x: x.basename):
                    sorted_files_dict[os.path.basename(rr.basename)] = rr.public_link
                print '*'*10
                print 'sorted_files_dict'
                print sorted_files_dict
                print '*'*10
                d[rt.display_name] = sorted_files_dict
                #d[rt.display_name] = {os.path.basename(x.basename):x.public_link for x in resource_set}
        if len(sorted_files_dict.keys()) > 0:
            bucket_string = '%s (Last modified %s)' % (bucket_name, date_string)
            bucket_dates.append((the_date,bucket_string))
            all_links[bucket_string] = d
    print '*'*20
    print 'all_links'
    print all_links
    print '*'*20

    # would like to order by the dates.  At the moment,bucket_dates is a list of tuples giving
    # the identifier (which is a key in the all_links dictionary) for the bucket and a datetime.
    # we then use that datetime to order the keys of the dictionary
    sorted_ids = sorted(bucket_dates, key=lambda x: x[0], reverse=True)
    sorted_dict = collections.OrderedDict()
    for date, key_string in sorted_ids:
       sorted_dict[key_string] = all_links[key_string] 
    print '?'*20
    print sorted_dict
    print '?'*20

    # want to check that files were not already downloaded:
    check_not_downloaded(sorted_dict, user)

    #tree = reformat_dict(all_links)
    tree = reformat_dict(sorted_dict)
    if len(user_buckets) == 0:
        error_msg = 'You do not have any sequencing projects associated with this email account (%s).' % user.email
    else:
        error_msg = ''
    return render(request, 'delivery/explorer.html', {
                'tree':json.dumps(tree) if tree else tree,
                'error_msg': error_msg
                })

def check_not_downloaded(sorted_dict, user):
	"""
	Checks the database table for whether a resource has been downloaded already by this user

	Note that the sorted_dict is of the following format:
	{
		'AB-12334':{
					'fastq':{
								'fileA.fastq.gz':'https://storage.cloud.google.com/....',
								'fileB.fastq.gz':'https://storage.cloud.google.com/....',
								'fileC.fastq.gz':'https://storage.cloud.google.com/....'
							}
					'compressed':{
								'fileA.zip':'https://storage.cloud.google.com/....'
							}
				}
	}
	Since we no longer have Resource objects, we use the https://storage.cloud.google.com/... links as unique identifiers for the files
	"""
	users_downloads = ResourceDownload.objects.filter(downloader = user)
	link_dict = {x.resource.public_link:x.download_date for x in users_downloads} # now have a dict of links that have been downloaded
	for bucket_name, download_dict in sorted_dict.items():
		for filetype, files_dict in download_dict.items():
			for basename, link in files_dict.items():
				if link in link_dict:
					download_time = link_dict[link]

					# drop the existing entry
					files_dict.pop(basename)

					# make another descriptive name to indicate file was downloaded already:
					newname = '%s (downloaded %s)' % (basename, download_time.strftime('%b %d, %Y'))
					files_dict[newname] = EXPIRED_LINK_MARKER


def reformat_dict(d):
        """
        Reformats the dictionary to follow the required format for the UI
        """
        o = []
        for key, value in d.items():
                if type(value) is dict or type(value) is collections.OrderedDict:
                        rv =reformat_dict(value)
                        new_d = {"text": key, "nodes":rv, "state":{"expanded": 0}}
                        o.append(new_d)
                else:
                        #o.append({"text": key, "href": value, "selectable": 1, "icon": "glyphicon glyphicon-unchecked", "selectedIcon": "glyphicon glyphicon-check", "state":{"expanded": 0, "selected":0}})
                        if value == EXPIRED_LINK_MARKER:
                                o.append({"text": key, "selectable":0, "state":{"expanded": 0, "disabled":1}})
                        else:
                                o.append({"text": key, "href": value, "state":{"expanded": 0}})
        return o
