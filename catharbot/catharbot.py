from olclient.openlibrary import OpenLibrary
import json
import olid

DEBUG=False

def ol_value_stringify(val):
    """
    Converts an OL json value to a string, regardless its type.
    borrowed from cdrini's jupyter notebook
    """
    if type(val) in [str, unicode]:
        return val.strip()
    elif type(val) in [int]:
        return str(val)
    elif isinstance(val, list):
        return "; ".join(map(ol_value_stringify, val))
    elif isinstance(val, dict):
        if val.keys() == ['key']:
            return extract_olid(val['key'])
        elif 'url' in val:
            return val['url']
        elif 'type' in val:
            if val['type'] == '/type/datetime':
                return val['value']
            # Why can both of these happen?
            elif (
                val['type'] == '/type/author_role'
                or val['type']['key'] == '/type/author_role' # This is the latest style
            ):
                return extract_olid(val['author']['key'])
            elif val['type']['key'] == '/type/link':
                return val['url']
            else:
                raise Exception("Cannot stringify dict with 'type' '%s'" % str(val))
        else:
            return str(val) # catch all?? is this safe?
            # raise Exception("Cannot stringify dict '%s'" % str(val))
    else: raise Exception("Cannot stringify value '%s'" % str(val))

def extract_olid(olid):
    """Convert a string like '/authors/OL1412764A' to just 'OL1412764A'"""
    return olid.split('/')[-1]


class CatharBot(OpenLibrary):

    def get_editions_from_work(self, id):
        if DEBUG:
            print id
        editions = [e.olid for e in self.Work.get(id).editions]
        return editions

    def get_move_edition(self, edition, work):
        url = self._generate_url_from_olid(edition)
        ed = self.session.get(url).json()
        ed['works'] = [{'key': "/works/" + work}]
        return ed

    def get_redirect(self, from_olid, to_olid):
        ''' from OLID, to OLID
        '''
        assert olid.get_type(from_olid) == olid.get_type(to_olid)
        data = {
            'key': olid.full_key(from_olid),
            'location': olid.full_key(to_olid),
            'type': { 'key': '/type/redirect' }
        }
        return data

    def merge_works(self, duplicate_works, master):
        docs = []
        for w in duplicate_works:
            editions = self.get_editions_from_work(w)
            for e in editions:
                docs.append(self.get_move_edition(e, master))
            docs.append(self.get_redirect(w, master))
        return docs

    def merge_editions(self, duplicate_editions, master):
        docs = []
        for e in duplicate_editions:
            docs.append(self.get_redirect(e, master))
        return docs

    def delete_list(self, ids, comment):
        docs = []
        for d in ids:
            docs.append({
                'key': olid.full_key(d),
                'type': '/type/delete'
            })
        return self.save_many(docs, comment)

    def save_many(self, docs, comment):
        headers = {
            'Opt': '"http://openlibrary.org/dev/docs/api"; ns=42',
            '42-comment': comment
        }
        return self.session.post(self.base_url+'/api/save_many', json.dumps(docs), headers=headers)

    def save_one(self, doc, comment):
        doc['_comment'] = comment
        return self.session.put(self.base_url + doc['key'] + ".json", json.dumps(doc))

    def is_modified(a, b):
        ''' Check if a string or doc has been modified
        '''
        return a != b

    def recurse_fix(self, data, fix_function, changed=False):
        ''' pass every field in a doc through a function
        '''
        if isinstance(data, basestring):  # only transforming strings at the moment
             return fix_function(data) 
        if isinstance(data, dict):
             output = {}
             for k, v in data.iteritems():
                 output[k] = self.recurse_fix(v, fix_function, changed)
             return output
        if isinstance(data, list):
             output = []
             for item in data:
                 output.append(self.recurse_fix(item, fix_function, changed))
             return output
        # no transform to do, return data
        return data 

    def load_doc(self, id):
        doc = self.session.get(olid.full_url(id)).json()
        if 'uri_descriptions' in doc:
            doc = self.fix_links(doc)
            # TODO: change 'subject_place' on editions to 'subject_places'?
        return doc

    def fix_links(self, doc):
        uris = self.merge_unique_lists([doc.get('url', []), doc.get('uris', [])])
        links = doc.get('links', [])
        for i,uri in enumerate(uris):
            links.append({'url': uri, 'title': doc['uri_descriptions'][i]})
        doc.pop('uri_descriptions')
        doc.pop('url')
        doc.pop('uris')
        doc['links'] = self.merge_unique_lists([links], )
        return doc

    def merge_unique_lists(self, lists, hash_fn=None):
        """ Combine unique lists into a new unique list. Preserves ordering."""
        result = []
        seen = set()
        for lst in lists:
            for el in lst:
                hsh = hash_fn(el) if hash_fn else el
                if hsh not in seen:
                    result.append(el)
                    seen.add(hsh)
        return result

    def merge_unique_dicts(self, key, docs):
        """ Combine unique dictionaries into a new unique dict."""
        merged = {}
        for d in docs:
            if key not in d:
                continue
            for sub_key, lst in d[key].items():
                for item in lst:
                    if item in merged.setdefault(sub_key, []):
                        continue
                    merged[sub_key].append(item)
        return merged

    def merge_docs(self, **kwargs):
        """ Returns a new dict which is the merge of the provided docs (work or edition).
        kwargs:
            master: Master edition OLID (dict - required)
          and one of
            duplicate: Duplicate edtion OLID (dict)
            duplicates: list of edition OLIDs ([dict])
        """

        master = kwargs['master']
        duplicates = kwargs.setdefault('duplicates', [])
        if 'duplicate' in kwargs:
            duplicates.append(kwargs['duplicate'])

        def merge(key, works):
            """
            Returns the result of merging the values of the keys from all the provided works. Gives
            preference to the first item in the list where appropriate.
            """
            # Keys whose value is a unique list
            UNIQUE_COMBINABLE_KEYS = {
                'authors',
                'covers',
                'excerpts',
                'links',
                'subject_people',
                'subject_times',
                'subject_places',
                'subjects',
                'lc_classifications',
                'dewey_number',
            # EDITIONS
                'contributors', # EDITIONS
                'contributions',
                'genres',
                'publishers',   # downcase and strip punctuation???
                'isbn_10',
                'isbn_13',
                'lccn',
                'oclc_numbers',
                'ia_box_id',
                'source_records',
                'series',
                'languages',
                'dewey_decimal_class',
                'other_titles',

            }
            COMBINABLE_DICTS = {
                'identifiers',     # EDITIONS
                'classifications', # EDITIONS

            }
            # Keys whose value is an item which should be chosen by order in the list
            PRECEDENCE_KEYS = {
                'type',
                'title',
                'description',
                'subtitle',
                'id',
                'first_publish_date', # Should technically be aggregated using min.
                'first_sentence',
                'number_of_editions',
              # EDITION KEYS
                'table_of_contents', # Complex!
                'ocaid',
                'weight',
                'number_of_pages',
                'pagination',
                'physical_format',
                'physical_dimensions',
                'publish_places',  # Could be combinable?
                'publish_country',
                'publish_date',  #  should pick the most specific valid date format
                'by_statement',
                'copyright_date',
                'works',
                'notes',
                'edition_name',
                'full_title',

            }
            # Readonly keys; always take from master
            READONLY_KEYS = {
                'created',
                'key',
                'last_modified',
                'latest_revision',
                'revision'
            }

            if key in UNIQUE_COMBINABLE_KEYS:
                return self.merge_unique_lists([w.get(key, []) for w in works], hash_fn=ol_value_stringify)
            elif key in COMBINABLE_DICTS:
                docs = works # naming! this is used for editions
                return self.merge_unique_dicts(key, docs)

            elif key in READONLY_KEYS:
                return works[0][key]
            elif key in PRECEDENCE_KEYS:
                # Get the value of the first work that has the key. Master if possible,
                # but take the value from another work if not.
                for w in works:
                    if key in w:
                        return w[key]
            else:
                raise Exception("Cannot handle key '%s'" % key)

        works = [master] + duplicates

        # all the keys we will have to merge
        keys = { key for work in works for key,val in work.items() }

        return { key: merge(key, works) for key in keys }

