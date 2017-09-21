#!/usr/bin/python

# Delete all works, edtitions, then authors of a Publisher
# Purpose: to remove early (2008) bulk imports of Audio CD catalogs
# Non-book items with bad author names

from catharbot import catharbot
import json

ol = catharbot.CatharBot()

def publishers_works(name, limit=100):
  data = ol.session.get(ol.base_url + "/publishers/" + name + ".json?limit=" + str(limit)).content
  works = [ol.Work.get(work['key'].replace('/works/', '')) for work in json.loads(data)['works']]
  return(works)

def editions_from_works(works):
  editions = []
  nonbooks = ["Audio CD", "Accessory"]
  for work in works:
    if 'M' in work.olid and hasattr(work, 'physical_format') and work.physical_format in nonbooks:
      print "Adding %s, Format: %s" % (work.title, work.physical_format)
      editions.append(work.olid)
    else:
      work.editions
      for e in work._editions:
        author = "???"
        phy_format = "???"
        if hasattr(e, 'physical_format') and e.physical_format in nonbooks:
            phy_format = e.physical_format
            if e.authors:
                author = e.authors[0].name
        print "Adding %s, by %s, Format: %s" % (e.title, author, phy_format)
        editions.append(e.olid)
  return(editions)

def authors_from_works(works):
  flatten = lambda l: [item for sublist in l for item in sublist]
  return flatten([ [a['author']['key'].replace('/authors/', '') for a in w.authors if 'author' in a] for w in works if hasattr(w, 'authors')])

def delete_authors(authors, comment="remove non-book authors"):
  deletes = []
  for au in authors:
     works = ol.session.get(ol.base_url + "/authors/" + au + "/works.json").json()
     if works['entries'] == []:
        deletes.append(au)
     else:
        print "Not deleting %s, still has works." % au 
  return ol.delete_list(deletes, comment)

def get_all_publisher(publisher_name, work_limit=500):
   """ gets all [works, editions, authors] olids of a publisher name
   """
   works = publishers_works(publisher_name, work_limit)
   editions = editions_from_works(works)
   authors = authors_from_works(works)
   w = [ work.olid for work in works ]
   return {'works': w, 'editions': editions, 'authors': authors}

def delete_all(items):
   print "Deleting %i editions" % len(items['editions'])
   print ol.delete_list(items['editions'], "remove non-book items")


   print "Deleting %i works" % len(items['works'])
   print ol.delete_list(items['works'], "remove non-book items")

   print "Deleting %i authors" % len(items['authors'])
   print delete_authors(items['authors'])
