import jinja2
import os
import sys

template_filepath = sys.argv[1]
output_path = sys.argv[2]

template_dir = os.path.abspath(os.path.dirname(template_filepath))
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
template = env.get_template(os.path.basename(template_filepath))
app_root = os.getenv('APP_ROOT')
cloud_sql_exec = os.path.join(app_root, os.getenv('CLOUD_SQL_PROXY'))
context = {'cloud_sql_exec': cloud_sql_exec, \
           'cloud_sql_dir':os.getenv('CLOUD_SQL_MOUNT'), \
           'google_project': os.getenv('GOOGLE_PROJECT'), \
            'credential_file': os.getenv('CRED_FILE_PATH')}

with open(output_path, 'w') as fout:
	fout.write(template.render(context))
