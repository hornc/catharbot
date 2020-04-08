#!/usr/bin/python

""" Collect duplicate ids into one json row
  input format:
<ocaid> <olid edition> (<olid work>)

  output:

{'key': '<ocaid>', 'olids': {'<olid work>': ['<olid edition>', ... ], '<olid work': ... }}
"""

import re
import sys


filename = sys.argv[1]

start_line = 0
end_line   = 0

def extract_ids(line):
    m = re.match(r'(^.+) (.+) (OL.+W)?', line)
    return m.groups()

def extract_work(line):
    return re.search(r'OL.+W', line).group(0)

with open(filename, 'r') as infile: 
    last_id = None
    group   = {}
    for i, line in enumerate(infile): 
        if end_line != 0 and i > end_line: 
            break 
        if i >= start_line:
            ocaid, olid, work = extract_ids(line)
            if last_id and ocaid != last_id:
                # end of group, operate on complete group
                output = {'olids': group, 'key': last_id} 
                #print "%i: %s" % (i, output)
                print output
                group = {}
            
            last_id = ocaid
            #data = bot.load_doc(olid) 
            #if not is_skippable(data) and data['ocaid'] == ocaid:
            group.setdefault(work, []).append(olid)

