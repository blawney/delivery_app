# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


class Bucket(models.Model):

	name = models.CharField(max_length=63)
	owners = models.ManyToManyField(User)

	def __str__(self):
		return self.name


class Resource(models.Model):

	bucket = models.ForeignKey(Bucket)
	basename = models.CharField(max_length=500)
	public_link = models.CharField(max_length=1000)
	resource_title = models.CharField(max_length=500)
	upload_date = models.DateTimeField(blank=True, null=True)

	class Meta:
		unique_together = (('bucket', 'basename'),)

	def __str__(self):
		return '%s(%s)' % (self.basename, self.bucket.name)

class ResourceDownload(models.Model):
	resource = models.ForeignKey(Resource)
	downloader = models.ForeignKey(User)
	download_date = models.DateTimeField(blank=True, null=True)

	def __str__(self):
		return '%s downloaded by %s on %s' % (self.resource.basename, self.downloader.email, self.download_date)


class DropboxTransferMaster(models.Model):
	owner = models.ForeignKey(User, default=None)
	start_time = models.DateTimeField(blank=True, null=True)
	name = models.CharField(max_length=500, default='', blank=True)

	def __str__(self):
		 return '%s' % self.name

class DropboxFileTransfer(models.Model):
	master = models.ForeignKey(DropboxTransferMaster, null=True, blank=True)
	start_time = models.DateTimeField(blank=True, null=True)
	finish_time = models.DateTimeField(blank=True, null=True)
	is_complete = models.BooleanField(default=False) # marked True whether successful transfer or not
	was_success = models.BooleanField(default=False) # flag in case of error
	source = models.CharField(max_length = 500, default='')
