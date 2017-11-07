import sys
import os
import subprocess

def make_call(command):
	process = subprocess.Popen(command, shell = True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
	stdout, stderr = process.communicate()
	if process.returncode != 0:
		print 'problem with copying static files!'
		sys.exit(1)


from ConfigParser import SafeConfigParser
config_parser = SafeConfigParser()
config_file = os.getenv('APP_CONFIG')
status = os.getenv('APP_STATUS')
if config_file and status:
        config_parser.read(config_file)
        # Depending on if dev or production, pull from a different section
        if status in config_parser.sections():
                environment = status
        else:
                print 'Need to choose one of the options for your environment: %s' % ','.join(config_parser.sections())
		sys.exit(1)
else:
        print 'Need to put a config ini file in your environment variables'
	sys.exit(1)


static_bucket = config_parser.get(environment, 'static_files_bucket')

command = 'gsutil -m cp -R static gs://%s/' % static_bucket
make_call(command)

# set public read on those resources:
command = 'gsutil -m acl ch -R -u AllUsers:R gs://%s' % static_bucket
make_call(command)
