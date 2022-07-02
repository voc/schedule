#!/usr/bin/env python3
# vim: set ts=4 sw=4 tw=0 et pm=:

# TODO: use argparser

import lxml.etree as ET

input_file = 'schedule.xcal'

with open(input_file) as f:
    schedule = f.read()

root = ET.fromstring(schedule)
doc = root.find('vcalendar')

for event in doc.findall('vevent'):
    if event.find('location').text in ['No', 'Pa', 'Re', 'Explody']:
        print(event.find('location').text + ': ' + event.find('summary').text)
        event.find('location').text = 'Stage: ' + event.find('location').text
    else:
        doc.remove(event)

ET.ElementTree(root).write('schedule-filtered.xcal')
