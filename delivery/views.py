# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import urllib
import httplib2
import json
import hashlib
import os

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
    for ub in user_buckets:
        print ub.name
        bucket_name = ub.name[len(settings.BUCKET_PREFIX):].upper()
        d = {}
        for rt in resource_types:
            resource_set = Resource.objects.filter(resource_type = rt, bucket = ub)
            d[rt.display_name] = {os.path.basename(x.basename):x.public_link for x in resource_set}
        all_links[bucket_name] = d
    print '*'*20

    tree = reformat_dict(all_links)
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
