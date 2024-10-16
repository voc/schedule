#!/bin/sh

# Test validation schemas against some example files

#wget 'https://api.events.ccc.de/congress/2023/schedule.xml' -O 37C3.xml
#xmlstarlet validate -e -s xsd/schedule.xml.xsd 37C3.xml

./xsd/validate_schedule_xml.sh https://api.events.ccc.de/congress/2023/schedule.xml