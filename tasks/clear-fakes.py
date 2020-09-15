#!/usr/bin/env python
from copy import copy
import sys
from olclient.openlibrary import OpenLibrary

"""
   Removes 'fake' ex-system subjects from Open Library works or editions.
   Takes as CLI argument a filename containing a list of Open Library keys:
   e.g.
     /works/OL1001319W
     /books/OL24710466M
"""

ol = OpenLibrary()

inlist = sys.argv[1]

fakes = ['overdrive', 'in library', 'accessible book', 'protected daisy', 'lending library', 'internet archive wishlist']
# only remove these from works:
wfakes = ['large type books', 'popular print disabled books']


otherbad = ['fictiion']

fakes += otherbad
changes_made = 0
with open(inlist, 'r') as f:
    for item in f:
        olid = item.strip().replace('/books/', '').replace('/works/', '')
        book = ol.get(olid)
        if not book.type.get('key') in ('/type/edition', '/type/work'):
            print("Unexpected type for %s -- Skipping!" % olid)
        else:
            orig_subjects = []
            if hasattr(book, 'subjects'):
                orig_subjects = copy(book.subjects)
            else:
                continue
            #print(olid)
            #print(u"%s: %s -- %s" % (olid, book.title, orig_subjects))
            targets = copy(fakes)
            if book.type['key'] == '/type/work':
                targets += wfakes
            removals = []
            for s in book.subjects:
                if s.lower() in targets:
                    #print("%s -- Fake subject %s found!" % (olid, s))
                    removals.append(s)
                if s.lower() != s: # remove duplicate lowercased subjects
                    if s.lower() in book.subjects:
                        #print("  Removing dupe lower(): %s" % s.lower())
                        removals.append(s.lower())
            for r in removals:
                try:
                    book.subjects.remove(r)
                except ValueError:
                    print(' unable to remove %s from %s -- probably already removed?' % (r, olid))
            if book.subjects != orig_subjects:
                #print("SUBJECTS CHANGED -- TO SAVE!")
                #print("New subjects: %s" % book.subjects)
                r = book.save('remove fake subjects')
                if r.status_code != 200:  # Only log unsuccessful saves
                    print('%s: %s' % (olid, r))
                else:
                    changes_made += 1
print('%s subject changes saved.' % changes_made)
