# schedule

Scripts to generate & validate [schedule files](https://c3voc.de/wiki/schedule) for events which use the [frab conference system][frab-website], [pretalx](https://github.com/pretalx/pretalx), or every other system able to generate schedule.json or CSV files in the correct format.

## rC3

see:
* https://c3voc.de/wiki/events:rc3:schedule
* https://github.com/voc/rC3_schedule
* https://git.cccv.de/rc3/schedule


## 36C3

TBD

see also:
* https://github.com/n0emis/36c3-guid-fixer/


## 34C3

see https://github.com/voc/schedule/blob/34C3/docs/data_flow_34C3_v0.7.pdf to get an overview and talk to @saerdnaer aka Andi if you have questions.

## Dependencies


### Debian and similar
``` bash
sudo apt-get install python python-pip python-lxml libxslt1-dev libxml2-utils
pip install -r requirements.txt
```

### macOS
``` bash
brew install python3
STATIC_DEPS=true pip3 install -r requirements.txt
```
or see https://stackoverflow.com/a/26544099/521791 on how to install lxml


[frab-website]: http://frab.github.io/frab/


