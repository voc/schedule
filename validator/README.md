# schedule.xml validate

Validates given schedule.xml against xsd file in same folder.

## Usage

```
 ./validate_schedule_xml.sh https://programm.froscon.de/2015/schedule.xml
```

## Requirements

  * xmllint
  * curl

## schedule.xml element requirements per software

  * c3tt
    * event: title
    * event: date
    * event attribute: id

  * mqtt fahrplan provider
    * conference: conference
    * conference: acronym
    * event: room
    * event: start
    * event: title
    * event: type
    * event: id
    * event: duration
    * event: start
    * event: end
