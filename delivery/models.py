# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


class Bucket(models.Model):

	name = models.CharField(max_length=63)
	owners = models.ManyToManyField(User)

	def __str__(self):
		return self.name

class ResourceType(models.Model):
	display_name = models.CharField(max_length=200)
	filename_suffix = models.CharField(max_length=200)
	def __str__(self):
		return self.display_name

class Resource(models.Model):

	bucket = models.ForeignKey(Bucket)
	basename = models.CharField(max_length=500)
	public_link = models.CharField(max_length=1000)
	resource_type = models.ForeignKey(ResourceType)
	upload_date = models.DateTimeField(blank=True, null=True)
