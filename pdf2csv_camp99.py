import sys

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice, TagExtractor
from pdfminer.converter import TextConverter, PDFConverter
from pdfminer.pdfpage import PDFPage
from pdfminer.cmapdb import CMapDB
from pdfminer.layout import LAParams
from pdfminer.image import ImageWriter

from collections import OrderedDict
from StdSuites.AppleScript_Suite import events
from _sqlite3 import Row

# main
def main(argv):
    '''
    import getopt
    def usage():
        print ('usage: %s  file.pdf ' % argv[0])
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'dp:m:P:o:CnAVM:L:W:F:Y:O:R:St:c:s:')
    except getopt.GetoptError:
        return usage()
    if not args: return usage()
    '''
    # debug option
    debug = 0

    # output option
    outfile = None
    outtype = 'text'
    layoutmode = 'normal'
    codec = 'utf-8'
    pageno = 1
    laparams = LAParams()
    pagenos = set()

    #
    PDFDocument.debug = debug
    PDFParser.debug = debug
    CMapDB.debug = debug
    PDFPageInterpreter.debug = debug
    #
    rsrcmgr = PDFResourceManager()

    if outfile:
        outfp = file(outfile, 'w')
    else:
        outfp = sys.stdout
    
    
    class ScheduleConverter(TextConverter):

        # the pdfminer api does not really allow to return results into a variable
        # therefore we have to use a global variable where the data is written to
        events = []

        def __init__(self, rsrcmgr, outfp, laparams=laparams):
            TextConverter.__init__(self, rsrcmgr, outfp, laparams=laparams)
            return
    
        def receive_layout(self, ltpage):
            
            from pdfminer.layout import LTContainer, LTPage, LTText
            from pdfminer.layout import LTTextBox, LTTextBoxVertical, LTTextGroup
            from pdfminer.layout import LTContainer, LTPage, LTText, LTLine, LTRect, LTCurve
            from pdfminer.layout import LTFigure, LTImage, LTChar, LTTextLine, LTAnno
            from pdfminer.layout import LTTextBox, LTTextBoxVertical, LTTextGroup, LTTextLineHorizontal
            
            left = []
            right = []
            
            def render(item):
                global self
                
                if isinstance(item, LTContainer):
                    for child in item:
                        render(child)
                if isinstance(item, LTTextBox):
  
                    # the order of the individual items boxes is mixed
                    # we have two coulums therefore, we can use the 
                    # positioning of the text on the page as seperator
                    # 288 units is the center of the page in our test case. 
                    if item.x0 < 288:
                        left.append(item)
                    else:
                        # normalize coordinates
                        item.x0 -= 288
                        item.x1 -= 288
                        right.append(item)
                        
            render(ltpage)
            
            # the first element is the headline with day
            day = left.pop(0)._objs[1].get_text().strip();
            rooms = [left, right]

            # iterate over alls rooms
            for items in rooms:
                room = items.pop(0).get_text().strip();
                
                # group items into individual events
                events_raw = []
                event = []
                for item in items:
                    if int(item.x0) == 50:
                        # if event is empty, e.g. has only a time but nothing else ignore,
                        #  otherwise store event into events_raw list
                        if len(event) > 1:
                            events_raw.append(event)
                        event = []
                    event.append(item)
                # store last event into events_raw list
                if len(event) > 1:
                    events_raw.append(event)
                # debug
                #for x in events_raw:
                #    print [ y.get_text() for y in x ]
                
                
                for event_r in events_raw:
                    event = OrderedDict()
                    event['day'] = day
                    event['start_hour'] = event_r.pop(0).get_text().strip();
                    event['room'] = room
                    event['persons'] = []
                    
                    event_p = []
                    
                    #print event_r
                    
                    for item in event_r:
                        # filter out person items
                        if item.x1 < 62:
                            p = item.get_text()
                            p = " ".join(p.split())
                            event['persons'].append(p)
                        else:
                            event_p.append(item.get_text())

                    event['title'] = event_p.pop(0).strip()
                    event['description'] = "\n".join([x for x in event_p])
                    
                    self.events.append(event)
                    #print event
                #'''
            self.write_text('\f')
            return
        def sort_events(self):
            self.events = sorted(self.events, key = lambda x: (x['day'], x['start_hour'], x['room']))
    
        
    device = ScheduleConverter(rsrcmgr, outfp, laparams=laparams)

    
    fname = 'camp99_workshops-1.2.pdf'
    with open(fname, 'rb') as fp:
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.get_pages(fp, pagenos, check_extractable=True):
            interpreter.process_page(page)
    device.sort_events()

    with open('camp99_workshops.csv', 'w') as f:
        #writer = csv.writer(output, delimiter=',')
        #writer.writerows(enumerate(device.events, 1))
        
        w = csv.DictWriter(f, device.events[0].keys(), quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in device.events:
            row_n = row.copy()
            row_n['persons'] = ", ".join(row_n['persons'])
            
            #http://stackoverflow.com/questions/5838605/python-dictwriter-writing-utf-8-encoded-csv-files
            w.writerow({k:v.encode('utf8').strip() for k,v in row_n.iteritems()} )

    device.close()
    
    print 'done'
    
    outfp.close()
    return


if __name__ == '__main__': sys.exit(main(sys.argv))