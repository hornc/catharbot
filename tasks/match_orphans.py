#!/usr/bin/python

"""
Script to correct Orphaned Editions with OCAIDs.

Edition's unique identifiers are used to search for existing works, and associated.
If no existing works are found, and new work is created for the edition.

Unique identifiers used for searching: ISBN, LCCN, OCLC numbers 

"""

import json
import sys
import os
import re
import time
from catharbot import catharbot

def skippable(doc):
    """ Skip if the record has already been deleted, redirected, OR already has a work """
    if doc['type']['key'] in ['/type/delete', '/type/redirect']:
        return True
    if 'works' in doc:
        return True
    else:
        return False 

def search_all_ids(ids):
    # eg input {'lccn': ['1234'], 'oclc': ['1234'], 'isbn': ['1234', '5678']}
    query = '%20+OR+'.join([ k + ':' + v for (k, id_list) in ids.iteritems() for v in id_list ])
    #print "DEBUG: %s" % query
    if query == "":
        return []
    try:
        results = bot.session.get(bot.base_url + '/search.json?q=' + query + '&limit=2')
        return [ x['key'] for x in results.json()['docs'] if x['key'][-1] == 'W' and x['edition_count'] < 100 ]
    except Exception, e:
        print "ERROR: Unable to parse search results for %s => %s Trying again..." % (ids, e)
        time.sleep(2)
        return search_all_ids(ids)


def get_works_from_identifier(identifier_type, value):
    try:
        results = bot.session.get(bot.base_url + '/search.json?q=' + identifier_type + '%3A' + value)
        return [ x['key'] for x in results.json()['docs'] if x['key'][-1] == 'W' ]
    except Exception, e:
        print "ERROR: Unable to parse search results for %s: %s -> %s Trying again..." % (identifier_type, value, e)
        time.sleep(5)
        return get_works_from_identifier(identifier_type, value)

def get_works_from_isbn(isbn):
    results = bot.session.get(bot.base_url + '/search.json?q=isbn%3A' + isbn).json()
    return [ x['key'] for x in results['docs'] if x['key'][-1] == 'W' ]

def create_work_from_edition(edition):
    """ based on https://github.com/internetarchive/openlibrary/blob/master/openlibrary/plugins/upstream/addbook.py#L623 """
    work = {
        'type': {'key': '/type/work'},
        'title': edition['title'],
        'authors': [{'type': '/type/author_role', 'author': {'key': a['key']}} for a in edition.get('authors', [])],
    }
    if 'subjects' in edition:
        work['subjects'] = edition['subjects']
    if 'covers' in edition:
        work['covers'] = edition['covers']
    work.setdefault('subjects', []).extend([u'In Library', u'Protected DAISY'])
    if MAKE_CHANGES:
        r = bot.session.post(bot.base_url + '/api/new.json', json.dumps(work))
        if r.status_code != 200:
            print "ERROR on %s: %i-- %s" % (edition['key'], r.status_code, r.content)
    else:
       print "DEBUG: %s" % work
       return "OL_DEBUG_W" 
    # return the new work's OLID
    return re.search(r'OL\d+W', r.content).group()

def clean_string(title):
    res = title.strip()
    if re.match("^.+[^\.]\.$", res):
        res = res[:-1]
    return res

def clean_book(book_data):
    """ Removes spaces and single period on work/edition titles and subjects """
    if 'title' in book_data:
        book_data['title'] = clean_string(book_data['title'])
    if 'subjects' in book_data:
        book_data['subjects'] = [ clean_string(s) for s in book_data['subjects'] ]
    return book_data

def get_live_edition(olid):
    try:
       return bot.load_doc(olid)
    except:
       time.sleep(5)
       return get_live_edition(olid)

if __name__ == '__main__':
   MAKE_CHANGES = True 
   CREATE_NEW   = False
   # takes a OL editions dump file, filteredi by line, as input
   filename = sys.argv[1]

   # input file line number to start from and number of records to process
   start   = int(sys.argv[2])
   records = int(sys.argv[3])
   #start   = 119
   #records = 10 

   bot = catharbot.CatharBot()

   with open(filename, 'r') as infile:
        for i, line in enumerate(infile):
            if i > (start + records):
                break
            if i >= start:
                parts = line.split("\t")
                olid = parts[1].replace('/books/', '')
               
                live_edition = get_live_edition(olid)

                if skippable(live_edition):
                    print "%i: Skipping %s" % (i, olid)
                    continue

                data = live_edition
                #results = []
                # also check by lccn or oclc !!!!

                # send off one query for all ids
                lccns = data.get('lccn', [])
                oclcs = data.get('oclc_numbers', [])
                isbns = data.get('isbn_13', []) + data.get('isbn_10', [])

                results = []
                #results = search_all_ids({'lccn': lccns, 'oclc': oclcs, 'isbn': isbns}) 

                if 'lccn' in data and len(results) == 0:
                    results += [ work for lccn in data['lccn'] for work in get_works_from_identifier('lccn', lccn) ]

                if 'oclc_numbers' in data and len(results) == 0:
                    results += [ work for oclc in data['oclc_numbers'] for work in get_works_from_identifier('oclc', oclc) ]

                if ('isbn_13' in data or 'isbn_10' in data) and len(results) == 0:
                    #isbns = data.get('isbn_13', []) + data.get('isbn_10', [])
                    results += search_all_ids({'isbn': isbns})
                    #results += [ work for isbn in isbns for work in get_works_from_identifier('isbn', isbn) ]

                if CREATE_NEW and results == []:
                    try:
                        work_olid = create_work_from_edition(clean_book(live_edition))
                        updated_ed = clean_book(bot.get_move_edition(olid, work_olid))
                        if MAKE_CHANGES:
                            bot.save_one(updated_ed, "associate with new work")
                        print "%i: No existing works found. Create new work for %s => %s" % (i, olid, work_olid)
                    except:
                        print "Unable to create and associate work for %s" % olid
                elif len(results) > 0:
                    master = results[0].replace('/works/', '')
                    updated_ed =  clean_book(bot.get_move_edition(olid, master))
                    if MAKE_CHANGES:
                        bot.save_one(updated_ed, "associate with existing work")
                    print "%i: %i existing works found. Associate %s with %s" % (i, len(results), olid, master)
                else:
                    print "%i: Not creating new record for %s" % (i, olid)

