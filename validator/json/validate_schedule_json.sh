#!/bin/sh
check-jsonschema --schemafile schema2.json \
  ./examples/hub-schedule2.json

check-jsonschema --schemafile schema.json \
  ./examples/pretalx-democon.json
#  ./examples/pretalx-rc3.json # Additional properties are not allowed ('answers' was unexpected)
#  ./examples/frab-camp2019.json  has to many validation errors, so we skip it for now. 