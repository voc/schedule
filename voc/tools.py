from collections import OrderedDict

sos_ids = {}
next_id = 100

def set_base_id(value):
    global next_id
    next_id = value

def get_id(guid):
    global sos_ids, next_id
    if guid not in sos_ids:
        #generate new id
        sos_ids[guid] = next_id
        next_id = next_id + 1  
    
    return sos_ids[guid]


def copy_base_structure(subtree, level):  
    ret = OrderedDict()
    if level > 0:
        for key, value in subtree.iteritems():
            if isinstance(value, (basestring, int)):
                ret[key] = value
            elif isinstance(value, list):
                ret[key] = copy_base_structure_list(value, level-1) 
            else:
                ret[key] = copy_base_structure(value, level-1) 
    return ret

def copy_base_structure_list(subtree, level):  
    ret = []
    if level > 0:
        for value in subtree:
            if isinstance(value, (basestring, int)):
                ret.append(value)
            elif isinstance(value, list):
                ret.append(copy_base_structure_list(value, level-1))
            else:
                ret.append(copy_base_structure(value, level-1)) 
    return ret




from lxml import etree as ET
#from xml.etree import cElementTree as ET

def dict_to_attrib(d, root):
    assert isinstance(d, dict)
    for k,v in d.items():
        assert _set_attrib(root, k, v)
            
def _set_attrib(tag, k, v):
    if isinstance(v, basestring):
        tag.set(k, v)
    elif isinstance(v, int):
        tag.set(k, str(v))
    else:
        print "  error: unknown attribute type %s=%s" % (k, v)



# dict_to_etree from http://stackoverflow.com/a/10076823

# TODO:
#  * check links conversion
#  * ' vs " in xml
#  * logo is in json but not in xml

def dict_to_schedule_xml(d):
    root_node = None
    
    
    def _to_etree(d, node, parent = ''):
        if not d:
            pass
        elif isinstance(d, basestring):
            node.text = d
        elif isinstance(d, int):
            node.text = str(d)
        elif (isinstance(d, dict) or isinstance(d, OrderedDict)):
            count = len(d)
            for k,v in d.items():
                if parent == 'day':
                    if k[:4] == 'day_':
                        # remove day_ prefix from items
                        k = k[4:]
                    if k == 'index':
                        # in json the first index is 0, in the xml the first day has index 1
                        v += 1
                
                if k == 'id' or k == 'guid' or (parent == 'day' and isinstance(v, (basestring, int))):
                    _set_attrib(node, k, v)
                    count -= 1
                elif k == 'url' and parent == 'link':
                    _set_attrib(node, 'href', v)
                    count -= 1
                elif count == 1 and isinstance(v, basestring):
                    node.text = v
                # elif k.startswith('#'):
                #    assert k == '#text' and isinstance(v, basestring)
                #    print count
                #    node.text = v
                # elif k.startswith('@'):
                #    assert isinstance(v, basestring)
                #    _set_attrib(node, k[1:], v)
                else:
                    node_ = node

                    if parent == 'room':
                        node.set('name', k)
                        k = 'event'
                        
                    if k == 'days':
                        # in the xml schedule days are not a child of a conference, but directly in the document node
                        node_ = root_node     
                    
                    # special handing for collections: days, rooms etc.
                    if k[-1:] == 's':              
                        # don't ask me why the pentabarf schedule xml schema is so inconsistent... --Andi 
                        # create collection tag for specific tags, e.g. persons, links etc.
                        if parent == 'event':
                            node_ = ET.SubElement(node, k)
                        
                        # remove last char (which is an s)
                        k = k[:-1] 
                    # different notation for conference length in days
                    elif parent == 'conference' and k == 'daysCount':
                        k = 'days'
                    
                    if isinstance(v, list):
                        for element in v:
                            _to_etree(element, ET.SubElement(node_, k), k)
                    else:
                        _to_etree(v, ET.SubElement(node_, k), k)
        else: assert d == 'invalid type'
    #print d
    assert isinstance(d, dict) and len(d) == 1
    tag, body = next(iter(d.items()))

    root_node = ET.Element(tag)
    _to_etree(body, root_node)
    return ET.tostring(root_node, pretty_print = True)