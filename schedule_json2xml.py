#!/usr/bin/python
# vim: set ts=4 sw=4 tw=0 et pm=:

import getopt, sys 
import os.path
import json
from collections import OrderedDict
import voc.tools

options, remainder = getopt.getopt(sys.argv[1:], 
    'i:o', 
    ['in=', 'out=']
)

input_file = None
output_file = None

for opt, arg in options:
    if opt in ('-i', '--in'):
        input_file = arg
        if output_file is None:
            output_file = os.path.splitext(input_file)[0] + ".xml"
    if opt in ('-o', '--out'):
        output_file = arg

if input_file is None:
    print " Usage: " + os.path.basename(sys.argv[0]) + " -i input.json [-o output.xml]"
    exit(-1)

# do the actual work

with open(input_file) as f:
    schedule_json = f.read()
schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule_json)

with open(output_file, 'w') as f:
    f.write(voc.tools.dict_to_schedule_xml(schedule))