#!/bin/bash

echo "working dir:"`pwd`

# input args:
# determines whether production of dev.  Must match a section in the config file below
export APP_STATUS=$1
if [ $1 == "dev" ]; then
  echo "Setting up development environment"
  export GOOGLE_PROJECT=cccb-sandbox-164319
  export DEVPORT=$4
else
  echo "Setting up production environment"
  export GOOGLE_PROJECT=cccb-data-delivery
fi


# path to a google bucket.  Include gs:// prefix!  This bucket has credential files, etc.. 
APP_CONFIG_BUCKET=$2

# Path to a JSON credential file (service account credentials) on the docker container's filesystem
# This file allows us to authenticate with gcloud, so that we can then pull the remainder of the configuration
# files, etc. from the bucket
export CRED_FILE_PATH=$3 

# start the python virtualenv
source $DJANGO_VENV/bin/activate

# get gsutil up and running.  We first authenciate with gcloud which allows us to use gcloud
$GCLOUD auth activate-service-account --key-file=$CRED_FILE_PATH
SERVICE_ACCOUNT=$(python /startup/get_account_name.py $CRED_FILE_PATH)
export BOTO_PATH=/root/.config/gcloud/legacy_credentials/$SERVICE_ACCOUNT/.boto

# pull the various credential and config files:
gsutil cp $APP_CONFIG_BUCKET/sequencing_delivery.config .
export APP_CONFIG=`pwd`/sequencing_delivery.config

# copy the parameterized settings file to settings.py.  For the moment this is done to 
# avoid messing with the production application, but this will eventually be removed as settings_config.py 
# is debugged
cp sequencing_delivery/settings_config.py sequencing_delivery/settings.py

mkdir credentials
gsutil cp $APP_CONFIG_BUCKET/*credentials.json credentials/
cp $CRED_FILE_PATH credentials/
export SERVICE_ACCOUNT_CREDENTIALS=credentials/$(basename $CRED_FILE_PATH)

# start supervisor:
mkdir -p /etc/supervisor/conf.d
cp /startup/supervisord.conf /etc/supervisord.conf
supervisord --configuration /etc/supervisord.conf

# fill out the conf file for the cloud SQL proxy and put it in the correct location:
python /startup/fill_cloud_sql_template.py /startup/cloud_sql.template.conf /etc/supervisor/conf.d/cloud_sql.conf

# start the connection to the database:
#$CLOUD_SQL_PROXY -dir $CLOUD_SQL_MOUNT \
#    -projects=$GOOGLE_PROJECT \
#    -credential_file=$CRED_FILE_PATH &
#sleep 5

# get supervisor going so we can use the cloud sql database:
supervisorctl reread
supervisorctl update
sleep 5 # wait for cloud sql to make connection

# make django migrations if necessary:
python /startup/ensure_migrations.py $APP_ROOT
python manage.py makemigrations
python manage.py migrate

# copy the redis conf file to the proper location
cp /startup/redis.conf /etc/supervisor/conf.d/redis.conf

# celery-related:
python /startup/fill_template.py /startup/celery_worker.template.conf /etc/supervisor/conf.d/celery_worker.conf
python /startup/fill_template.py /startup/celery_beat.template.conf /etc/supervisor/conf.d/celery_beat.conf
mkdir -p /var/log/celery
touch /var/log/celery/cccb_celery_beat.log
touch /var/log/celery/cccb_celery_worker.log
supervisorctl reread
supervisorctl update

# ensure that the current static files are sent to the bucket to serve them.
python /startup/copy_static_assets.py

# create the admin:
python sequencing_delivery/create_superuser.py

# Start Gunicorn processes
mkdir -p /var/log/gunicorn
export APP_STATUS=$1
if [ $1 == "dev" ]; then
  echo "Starting gunicorn in development environment"
  LOG="/var/log/gunicorn/gunicorn"$DEVPORT".log"
  touch $LOG
  SOCKET_PATH="unix:/host_tmp/gunicorn"$DEVPORT".sock"
  exec gunicorn sequencing_delivery.wsgi:application \
	--bind $SOCKET_PATH \
	--workers 1 \
	--error-logfile $LOG \
	--log-file $LOG
else
  echo "Setting up production environment"
  export GOOGLE_PROJECT=cccb-data-delivery
  LOG="/var/log/gunicorn/gunicorn.log"
  touch $LOG
  SOCKET_PATH="unix:/host_tmp/gunicorn.sock"
  exec gunicorn sequencing_delivery.wsgi:application \
	--bind $SOCKET_PATH \
	--workers 3 \
	--error-logfile $LOG \
	--log-file $LOG
fi
