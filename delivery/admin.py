# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from models import Bucket, Resource, DropboxTransferMaster, DropboxFileTransfer, ResourceDownload

class ResourceAdmin(admin.ModelAdmin):
	list_display = ('bucket', 'basename','public_link','resource_title', 'upload_date')
	list_editable = ('resource_title',)

class BucketAdmin(admin.ModelAdmin):
	list_display = ('name',)

class DropboxTransferMasterAdmin(admin.ModelAdmin):
	list_display = ('start_time','name', 'owner')
	list_editable = ('name',)

class DropboxFileTransferAdmin(admin.ModelAdmin):
	list_display = ('master', 'source', 'is_complete', 'was_success')

class ResourceDownloadAdmin(admin.ModelAdmin):
	list_display = ('resource','downloader','download_date')


admin.site.register(Bucket, BucketAdmin)
admin.site.register(Resource, ResourceAdmin)
admin.site.register(ResourceDownload, ResourceDownloadAdmin)
admin.site.register(DropboxTransferMaster, DropboxTransferMasterAdmin)
admin.site.register(DropboxFileTransfer, DropboxFileTransferAdmin)
