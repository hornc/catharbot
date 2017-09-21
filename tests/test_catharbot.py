from catharbot.catharbot import CatharBot
import pytest

class TestCatharbot:
    @pytest.fixture()
    def bot(self):                                                      
        return CatharBot()

    def test_merge_unique_lists(self, bot):
 
        test_data = [
            {'in': [[1,2], [2,3]], 'expect': [1, 2, 3]}, 
            {'in': [[1,2,2,2], [2, 2, 3]], 'expect': [1, 2, 3]}, 
            {'in': [[9, 10]], 'expect': [9, 10]},
            {'in': [[1, 1, 1, 1]], 'expect': [1]},
            {'in': [], 'expect': []},
            {'in': [[2], [1]], 'expect': [2, 1]}
        ]

        for case in test_data:
            assert(bot.merge_unique_lists(case['in']) == case['expect'])

    def test_merge_into_work(self, bot):
        master = {'covers': [1], 'title': 'The Work'}
        b = {'title': 'the work', 'covers': [2 , 3, 4]}

        result = bot.merge_into_work(master, [b])
        assert(result['title'] == 'The Work')
        assert(result['covers'] == [1, 2, 3, 4])

    def test_dict_of_list_merge(self, bot):
        master = { 'identifiers': { 'foo': [1, 2], 'bar': ['A'] } }
        dupe   = { 'identifiers': { 'foo': [3, 4], 'bar': ['B'], 'baz': ['C'] } }

        result = bot.merge_into_work(master, [dupe])
        assert(result['identifiers'] == {'foo': [1, 2, 3, 4], 'bar': ['A', 'B'], 'baz': ['C'] })

    def xtest_live_work_merge(self, bot):
        master = bot.load_doc('OL16795190W')
        dupe   = bot.load_doc('OL16795115W')
        result = bot.merge_into_work(master, [dupe])

    def xtest_live_edition_merge(self, bot):
        master = bot.load_doc('OL25415823M')
        dupe   = bot.load_doc('OL25415725M')
        result = bot.merge_into_work(master, [dupe])

