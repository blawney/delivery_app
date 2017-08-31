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

from models import Bucket, ResourceType, Resource

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
                date_string = last_upload_date.strftime('%B %d, %Y')
                the_date = last_upload_date
                d[rt.display_name] = {os.path.basename(x.basename):x.public_link for x in resource_set}
        if len(d.keys()) > 0:
            bucket_string = '%s (Last modified %s)' % (bucket_name, date_string)
            bucket_dates.append((the_date,bucket_string))
            all_links[bucket_string] = d

    # would like to order by the dates.  At the moment,bucket_dates is a list of tuples giving
    # the identifier (which is a key in the all_links dictionary) for the bucket and a datetime.
    # we then use that datetime to order the keys of the dictionary
    sorted_ids = sorted(bucket_dates, key=lambda x: x[0], reverse=True)
    sorted_dict = collections.OrderedDict()
    for date, key_string in sorted_ids:
       sorted_dict[key_string] = all_links[key_string] 

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


def reformat_dict(d):
        """
        Reformats the dictionary to follow the required format for the UI
        """
        o = []
        for key, value in d.items():
                if type(value) is dict:
                        rv =reformat_dict(value)
                        new_d = {"text": key, "nodes":rv, "state":{"expanded": 0}}
                        o.append(new_d)
                else:
                        #o.append({"text": key, "href": value, "selectable": 1, "icon": "glyphicon glyphicon-unchecked", "selectedIcon": "glyphicon glyphicon-check", "state":{"expanded": 0, "selected":0}})
                        o.append({"text": key, "href": value, "state":{"expanded": 0}})
        return o
