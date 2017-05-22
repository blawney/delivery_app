# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from models import Bucket, Resource, ResourceType

class ResourceTypeAdmin(admin.ModelAdmin):
	list_display = ('display_name','filename_suffix')
	list_editable = ('filename_suffix',)

class ResourceAdmin(admin.ModelAdmin):
	list_display = ('bucket', 'basename','public_link','resource_type')
	list_editable = ('resource_type',)

class BucketAdmin(admin.ModelAdmin):
	list_display = ('name',)
	#list_editable = ('name',)

admin.site.register(Bucket, BucketAdmin)
admin.site.register(Resource, ResourceAdmin)
admin.site.register(ResourceType, ResourceTypeAdmin)
