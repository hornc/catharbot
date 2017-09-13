from olclient.openlibrary import OpenLibrary
import json
ol = OpenLibrary()

DEBUG=True

def get_editions_from_work(olid):
    if DEBUG:
        print olid
    editions = [e.olid for e in ol.Work.get(olid).editions]
    return editions

def get_move_edition(edition, work):
    url = ol._generate_url_from_olid(edition)
    ed = ol.session.get(url).json()
    ed['works'] = [{'key': "/works/" + work}]
    return ed

def get_redirect(from_key, to_key):
        data = {
                'key': from_key,
                'location': to_key,
                'type': { 'key': '/type/redirect' }
               }
        return data

def merge_works(duplicate_works, master):
    docs = []
    for w in duplicate_works:
        editions = get_editions_from_work(w)
        for e in editions:
            docs.append(get_move_edition(e, master))
        docs.append(get_redirect('/works/' + w, '/works/' + master))
    return save_many(docs, "Merged duplicate works")

def save_many(docs, comment):
    headers = {
        'Opt': '"http://openlibrary.org/dev/docs/api"; ns=42',
        '42-comment': comment
    }
    return ol.session.post(ol.base_url+'/api/save_many', json.dumps(docs), headers=headers)