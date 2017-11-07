import jinja2
import os
import sys

template_filepath = sys.argv[1]
output_path = sys.argv[2]

template_dir = os.path.abspath(os.path.dirname(template_filepath))
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
template = env.get_template(os.path.basename(template_filepath))
context = {'app_root': os.getenv('APP_ROOT'), \
           'venv': os.getenv('DJANGO_VENV')}

with open(output_path, 'w') as fout:
	fout.write(template.render(context))
