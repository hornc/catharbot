#!/usr/bin/python

from catharbot import catharbot
import ast
import sys

"""
Input file format:

{'key': '<ocaid>', 'olids': {'<olid work>': ['<olid edition>', ... ], '<olid work': ... }}

Usage:
    ./merge_dupes.py <filename> <start_line> <records_to_process>
"""

def extract_olid(olid):
    """Convert a string like '/authors/OL1412764A' to just 'OL1412764A'"""
    return olid.split('/')[-1]

def remove_editions(duplicates, docs):
    """ Removes editions by [OLID str] from a merge changeset docs ([JSON dicts])
        reason: to prevent duplicated edition documents that merge_works() reassigns
                and merge_editions() makes into redirects.
        TODO: refactor to make this process clearer / cleaner
    """
    return [ d for d in docs if extract_olid(d['key']) not in duplicates ]


def test_remove_editions():
    dupes = ['A', 'C']
    docs  = [{'key': '/books/A'}, {'key': '/books/B'}, {'key': '/books/C'}]
    assert(remove_editions(dupes, docs) == [{'key': '/books/B'}])


def full_merge(**kwargs):
    """ Merge identical editions and their works
        kwargs:
            master: Master edition OLID (str - required)
          and one of
            duplicate: Duplicate edtion OLID (str)
            duplicates: list of edition OLIDs ([str])
          simple: (bool) Do not merge data, just perform redirects, defaults to False
            Simple merge is faster and can be used when merging 'bad' data into a good record.
    """
    master = kwargs['master']
    simple = kwargs.setdefault('simple', False)
    duplicates = kwargs.setdefault('duplicates', [])
    if 'duplicate' in kwargs:
        duplicates.append(kwargs['duplicate'])
    #print "Merge %s into %s" % (duplicates, master)
    master_edition = bot.load_doc(master)
    dupe_editions = [ bot.load_doc(e) for e in duplicates ]
    changeset = []
    if not simple:
        merged_edition = bot.merge_into_work(master_edition, dupe_editions)
        changeset.append(merged_edition)
    # are there extra works to merge?
    master_w_olid = extract_olid(master_edition['works'][0]['key'])
    dupe_w_olids  = [ extract_olid(e['works'][0]['key']) for e in dupe_editions if extract_olid(e['works'][0]['key']) != master_w_olid ]
    if len(dupe_w_olids) > 1 or master_w_olid not in dupe_w_olids:
        master_work = bot.load_doc(master_w_olid)
        dupe_works  = [ bot.load_doc(w) for w in dupe_w_olids ]
        if not simple:
            merged_work = bot.merge_into_work(master_work, dupe_works)
            changeset.append(merged_work)
        changeset += bot.merge_works(dupe_w_olids, master_w_olid)
        # remove reassigned duplicate editions from changeset that will be made into redirects
        changeset = remove_editions(duplicates, changeset)
    changeset += bot.merge_editions(duplicates, master)
    return changeset



MAKE_CHANGES = True 

if __name__ == '__main__':

    CREATE_NEW   = False

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

            row = ast.literal_eval(line)

            # Not sure if this will get used, for re-processing output as input later
            if 'status' in row and row['status'] == 'done':
                continue

            duplicates = []
            master = None
            for work, editions in row['olids'].items():
                if master:
                    duplicates += editions
                else:
                    master = editions[0]
                    duplicates = editions[1:]
                 
            print "%s: Merge %s into %s" % (row['key'], duplicates, master)
            changes = full_merge(master=master, duplicates=duplicates)
            #print changes
            comment = "merge duplicate ocaids: %s" % row['key']

            if MAKE_CHANGES:
                bot.save_many(changes, comment)
