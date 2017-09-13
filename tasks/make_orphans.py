#!/usr/bin/python

import catharbot
import olid
import sys
import json
import ast
import re

filename = sys.argv[1]

"""
Input file format:

{'key': '<ocaid>', 'olids': {'<olid work>': ['<olid edition>', ... ], '<olid work': ... }}
"""

def count_works(row):
    return len(row['olids'])

def count_editions(row):
    editions = [ed for sublist in row['olids'].itervalues() for ed in sublist]
    return len(editions)

def is_orphan(record):
    return not 'works' in record

def load_orphans(row):
    current_orphans = []
    for work in row['olids']:
        if work is None:
            for ed in row['olids'][work]:
                data = bot.load_doc(ed) 
                if not skippable(data) and is_orphan(data):
                    current_orphans.append({'key': ed, 'data': data})
                else:  # remove it from the row
                    row['olids'][work].remove(ed)
    return current_orphans

def master_work(row):
    """ returns first good work """
    for work in row['olids']:
        if work != None:
            return work

def skippable(doc):
    ''' Skip if the record has already been deleted, redirected
        
    '''
    if doc['type']['key'] in ['/type/delete', '/type/redirect']:
        return True
    else:
        return False 

def merge_subjects(a, b):
    # take into account ALL subject fields (people, places &c)
    subjects = []
    if 'subjects' in a:
        subjects = a['subjects']
    if 'subjects' in b:
        subjects += b['subjects']
    subjects = set(subjects)
    print "Subjects: %s" % subjects
    return subjects 


def normalise(doc):
    doc.pop('key')
    if 'works' in doc:
        doc.pop('works')
    if 'created' in doc:
        doc.pop('created')
    doc.pop('last_modified')
    doc.pop('revision')
    if 'latest_revision' in doc:
        doc.pop('latest_revision')
    return doc

def identical(a, b):
    a_set = set(normalise(dict(a)))
    b_set = set(normalise(dict(b)))
    #merge_subjects(a, b)
    return a_set == b_set

def create_work_for(id):
    url = bot.session.get(olid.full_url(id).replace('.json', '')).url
    ed = bot.load_doc(id)
    ed['_comment'] = "create work for edition"
    return bot.session.post(url + '/edit', ed)


def add_subjects_to_work(subjects, w):
    mapping = {
        'subject': 'subjects',
        'place': 'subject_places',
        'time': 'subject_times',
        'person': 'subject_people',
    }
    for k, v in subjects.items():
        k = mapping[k]
        print v
        subjects = [i[0] for i in sorted(v.items(), key=lambda i:i[1], reverse=True) if i != '']
        existing_subjects = set(w.get(k, []))
        w.setdefault(k, []).extend(s for s in subjects if s not in existing_subjects)
        if w.get(k):
            w[k] = [unicode(i) for i in w[k]]
        try:
            assert all(i != '' and not i.endswith(' ') for i in w[k])
        except AssertionError:
            print 'subjects end with space'
            print w
            print subjects
            raise

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
    else:
       print "DEBUG: %s" % work
       return "OL_DEBUG_W" 
    # return the work OLID
    return re.search(r'OL\d+W', r.content).group()


def is_early_import(data):
    if data['revision'] > 3:
        return False
    #print "EARLY: %s" % data
    if 'created' in data and data['created']['value'][:4] in ['2008', '2009']:
        if 'last_modified' in data and int(data['last_modified']['value'][:4]) > 2010:
            return False
        return True
    return '2008' in data['last_modified']['value']

def update_row(row):
    """ update stored work data from OL"""
    output = {} 
    for w in row['olids']:
        if not w or len(row['olids'][w]) == 0:
            continue 
        data = bot.load_doc(w)
        if skippable(data):
            continue
        output[w] = row['olids'][w]
    row['olids'] = output
    return row 

# ../in_library_orphans2.txt 

start_line = 11
end_line = 20000 


MAKE_CHANGES = True

bot = catharbot.CatharBot()
with open(filename, 'r') as infile: 
    last_id = None
    group   = {}
    for i, line in enumerate(infile): 
        if end_line != 0 and i > end_line: 
            break 
        if i >= start_line:
            cols = line.split("\t") 
            olid = cols[1].replace('/books/', '')
            edition_data = json.loads(cols[4])
            ocaid = edition_data['ocaid']
            #print "%s\t%s" % (ocaid, olid)

            live_edition = bot.load_doc(olid)
            if skippable(live_edition) or 'works' in live_edition:
                print "%s\t%s" % (ocaid, live_edition['works'][0]['key'].replace('/works/', ''))
                
            else:
                work_olid = create_work_from_edition(live_edition)
                updated_ed =  bot.get_move_edition(olid, work_olid)
                if MAKE_CHANGES:
                    bot.save_one(updated_ed, "associate with work")
                print "%s\t%s" % (ocaid, work_olid)
         
