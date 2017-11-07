import json
import sys

j = json.load(open(sys.argv[1]))
sys.stdout.write(j['client_email'])
