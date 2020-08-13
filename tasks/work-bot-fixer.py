#!/usr/bin/env python3

import sys

from olclient.openlibrary import OpenLibrary

start = 19750
limit = 50


def is_work(thing):
    return thing.type['key'] == '/type/work'


if __name__ == '__main__':
    offset = int(sys.argv[1])
    ol = OpenLibrary()
    pos = start + offset * limit
    print('THIS POS', pos)
    #print('Workbot works w/o editions fixer')

    current_page = ol.session.get(ol.base_url + '/recentchanges.json?author=/people/WorkBot&offset=%d&limit=%d' % (pos, limit))
    i = 0
    if current_page.status_code == 200:
        page = current_page.json()
        first_date = page[0]['timestamp'][:10]
        print('DATE', first_date)
        for p in page:
            if p.get('comment') == 'merge works':
                  #print('FOUND %s' % p)
                  for c in p.get('changes') or []:
                      rev = c.get('revision', 2)
                      eprev = ol.session.get(ol.base_url + c.get('key') + '.json?v=%d' % (rev - 1))
                      if eprev.status_code == 200:
                           if eprev.json().get('works') is None:
                               # It's probably a work
                               #print('ORPHAN FOUND!', c.get('key'))
                               continue
                           wprev = eprev.json().get('works')[0].get('key').replace('/works/', '')
                           cedition = ol.get(c.get('key').replace('/books/', ''))
                           if cedition.work_olid is None: 
                               print('ERROR: problem getting work for %s' % c)
                               continue
                           wnext = cedition.work
                           w = ol.get(wprev)
                           #print(w.olid, w.editions)
                           if is_work(w) and not w.editions:
                               print('Work without editions found! %s' % w.olid)
                               print('    redirect to current work:', wnext.olid)
                               assert w.olid != wnext.olid
                               assert is_work(wnext)
                               redirect = ol.Redirect(f=w.olid, t=wnext.olid)
                               print(redirect.save('redirect to duplicate work'))
                               i += 1
    print(i, 'changes made.')

