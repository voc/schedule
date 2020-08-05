#!/bin/sh

xmllint_cmd=`command -v xmllint`
curl_cmd=`command -v curl`
xsd_file=`dirname $0`/schedule.xml.xsd

if [ -z "${xmllint_cmd}" ]; then
  echo "Please install xmllint!"
  exit 1
fi


if [ -z "${1}" ]; then
  echo "Please provide schedule xml http(s) URL."
  echo "  ${0} http://example.com/schedule.xml"
  exit 2
fi

if [ ! -e "${xsd_file}" ]; then
  echo "schedule.xml.xsd missing!"
  exit 3
fi

case "$1" in
  http://*|https://*)
    if [ -z "${curl_cmd}" ]; then
      echo "Please install curl!" >&2
      exit 4
    fi
    $curl_cmd $1 2>/dev/null | $xmllint_cmd --noout --schema ${xsd_file} -;;
  *)
    $xmllint_cmd --noout --schema ${xsd_file} $1;;
esac

xmllint_err=$?
if [ 0 -eq $xmllint_err ]; then
  echo
  echo "Yeeeeeah… ${1} validates ${xsd_file}!!1!"
fi

exit $?
