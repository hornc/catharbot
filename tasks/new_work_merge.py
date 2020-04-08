#!/usr/bin/python

from catharbot import catharbot
import sys

"""
Input file format:

tsv
ocaid master_work_olid dupe_work_olid ... Col8: siginificant_diffs 

Usage:
    ./new_work_merge.py <filename> <start_line> <records_to_process>
"""

def is_skippable(doc):
    """ Skip if the record has already been deleted or redirected."""
    return doc['type']['key'] in ['/type/delete', '/type/redirect']

def update_ia_sync(bot, ocaid, master, dupe):
    """ Update IA sync endpoint with the lendable edition after works have changed."""
    editions = bot.get(master).editions
    editions += bot.get(dupe).editions

    for e in editions:
        if 'ocaid' in e.json() and e.json()['ocaid'] == ocaid:
            print "Update IA sync with %s" % e.olid
            return bot.session.get(bot.base_url + "/admin/sync?edition_id=" + e.olid)


MAKE_CHANGES = True 

if __name__ == '__main__':

    filename = sys.argv[1]
    start   = int(sys.argv[2])
    records = int(sys.argv[3])

    bot = catharbot.CatharBot()

    with open(filename, 'r') as infile:
        for i, line in enumerate(infile):
            if i < start:
                continue
            if i >= (start + records):
                break

            data = line.split("\t")
            ocaid  = data[0]
            master = data[1].replace('/works/', '')
            dupe   = data[2].replace('/works/', '')
            title  = data[3]
            diffs  = int(data[7])
            if diffs > 0:
                raise Exception("Ooops, row %i [%s, %s] has %i significant diffs!" % (i, master, dupe, diffs))

            a = bot.load_doc(master)
            b = bot.load_doc(dupe)

            if is_skippable(a) or is_skippable(b):
                print "Skipping %i: %s, already merged/removed!" % (i, title)
                continue

            changes = bot.merge_works([dupe], master)
            changes.append(bot.merge_docs(master=a, duplicate=b))
            msg = "merge duplicate works of '%s'" % title
            print "%i: %s" % (i, msg)
            if MAKE_CHANGES:
                bot.save_many(changes, msg)

                # Update IA sync endpoint, after merging works
                print update_ia_sync(bot, ocaid, master, dupe)
