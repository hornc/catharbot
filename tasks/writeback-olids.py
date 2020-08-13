# iterate through archive.org items with onlt openlibrary
# and write back openlibrary_edition and openlibrary_work

import json
import sys
import time
import requests
from internetarchive import modify_metadata
from olclient.openlibrary import OpenLibrary

fname = sys.argv[1]

ol = OpenLibrary()

n = 0
with open(fname, 'r') as f:
   for line in f.readlines():
       data = json.loads(line)
       olid = data['openlibrary']
       ocaid = data['identifier']
       try: 
           e = ol.get(olid)
           wolid = e.work.olid
           assert wolid
       except requests.exceptions.HTTPError as e:
           print('404', olid, ocaid)
           wolid = None
       to_write = {
           'openlibrary_edition': olid
       }
       if wolid:
           to_write['openlibrary_work'] = wolid
       #print(ocaid, to_write)
       r = modify_metadata(ocaid, metadata=to_write)
       print('%s: %s' % (ocaid, r.status_code))
       n += 1
       if n > 300:
           print('PAUSE')
           time.sleep(900)
           n = 0 
