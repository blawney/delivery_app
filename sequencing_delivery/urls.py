"""sequencing_delivery URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin

import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^callback/', views.oauth2_callback),
    url(r'^login/', views.login, name='login'),
    url(r'^google-login/', views.google_login),
    url(r'^unauthorized/', views.unauthorized, name='unauthorized'),
    url(r'^$', views.default_home),
    url(r'^explorer/', include('delivery.urls')),
    url(r'^update/', views.update_db),
    url(r'^dbx/', views.dropbox_auth),
    url(r'^dbx-callback/', views.dropbox_callback),
    url(r'dbx-file-register', views.register_files_to_transfer),
    url(r'dropbox-transfer-complete', views.dropbox_transfer_complete),
]
