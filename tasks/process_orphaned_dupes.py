#!/usr/bin/python

from catharbot import catharbot, olid
import sys
import json
import ast
import re

"""
Input file format:

{'key': '<ocaid>', 'olids': {'<olid work>': ['<olid edition>', ... ], '<olid work': ... }}

Usage:
    ./process_dupes.py <filename> <start_line> <records_to_process>
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

def add_subjects_to_work(subjects, w):
    mapping = {
        'subject': 'subjects',
        'place': 'subject_places',
        'time': 'subject_times',
        'person': 'subject_people',
    }
    for k, v in subjects.items():
        k = mapping[k]
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

def create_work_from_edition(edition):
    """ based on https://github.com/internetarchive/openlibrary/blob/master/openlibrary/plugins/upstream/addbook.py#L623 """
    work = {
        'type': {'key': '/type/work'},
        'title': edition['title'],
        'authors': [{'type': '/type/author_role', 'author': {'key': a['key']}} for a in edition.get('authors', [])]
    }
    r = bot.session.post(bot.base_url + '/api/new.json', json.dumps(work))
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

# orphan_dupes.txt

MAKE_CHANGES = False

if __name__ == '__main__':

    CREATE_NEW   = False

    filename = sys.argv[1]
    start   = int(sys.argv[2])
    records = int(sys.argv[3])

    bot = catharbot.CatharBot()

    with open(filename, 'r') as infile:
        last_id = None
        group   = {}
        for i, line in enumerate(infile):
            if i < start:
                continue
            if i > (start + records):
                break

            row = ast.literal_eval(line)
            if 'status' in row and row['status'] == 'done':
                continue

            # is row a simple 2 edition row?
            #if count_editions(row) == 2 and count_works(row) == 2:
            #    print row

            # does row need merging?

            #data = bot.load_doc(olid) 
            #if not is_skippable(data) and data['ocaid'] == ocaid:
            orphans = load_orphans(row)
            row = update_row(row)
            print "ROW: %i" % i
            if count_works(row) <= 2:
                if len(orphans) == 0:
                    row['status'] = 'done'
                    print "FOUND A DONE ROW (no orphans)! %i" % i
                else:
                    print "\n  Orphans found: %s" % [ed['key'] for ed in orphans]
                    if len(orphans) == 2:
                        print "  Create Work from one edition, associate both editions with that work"
                        #print "  create work for %s (requires recaptcha :( )" % orphans[0]
                        # print create_work_for(orphans[0]['key'])
                        changes = []
                        comment = ""
                        if identical(orphans[0]['data'], orphans[1]['data']):
                            print "  IDENTICAL EDITIONS found -- redirect one to the other"
                            changes.append(bot.get_redirect(orphans[1]['key'], orphans[0]['key']))
                            del orphans[1]
                            comment = ", merge identical editions" 
                        if MAKE_CHANGES:
                            work_olid = create_work_from_edition(orphans[0]['data'])
                            for ed in orphans:
                                changes.append(bot.get_move_edition(ed['key'], work_olid))
                            print bot.save_many(changes, "associate with work" + comment)
                    elif len(orphans) == 1:
                        # print "  Check whether orphan edition is IDENTICAL to non-orphanded duplicate"
                        master = bot.load_doc(row['olids'][master_work(row)][0])
                        if identical(orphans[0]['data'], master):
                            print "  IDENTICAL EDITIONS found -- redirect one to the other -- TODO"
                        if is_early_import(orphans[0]['data']):
                            print "  Early (2008/2009) orphan detected, redirect to later import."
                            if MAKE_CHANGES:
                                r = bot.get_redirect(orphans[0]['key'], master['key'].replace('/books/', ''))
                                print bot.save_one(r, "merge edition") 
                        else:
                            print "  Associate lone orphan with work of dupe"
                            print "  Associate %s with %s" % (orphans[0]['key'], master_work(row))
                            if MAKE_CHANGES:
                                r = bot.get_move_edition(orphans[0]['key'], master_work(row))
                                print bot.save_one(r, "associate with work") 
                    else:
                        print "  Multiple orphans, unsure how to proceed......" 
            else:
                  print "  Multiple works found (%i), unsure how to proceed......" % count_works(row)
                  print "  Check for identical editions, merge down"
                  # changes = merge_down_editions(all_editions_in_row) # returns changed docs, 1st ed is master
                  # write changes to edtions
                  print "  Merge down to one work"
                  # merge down works to one work, 1st work is master
                  # write changes to works + editions

            print row
