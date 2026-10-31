import unittest
from copy import deepcopy
import _paths
from freshtray.choice_history import ChoiceHistory


class MemoryVault:
    def __init__(self): self.data={}
    def get(self,key): return self.data.get(key)
    def update(self,**values): self.data.update(deepcopy(values))


class ChoiceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.vault=MemoryVault();self.history=ChoiceHistory(self.vault)
        self.items=[{'id':1,'name':'Zebra'}, {'id':2,'name':'apple'}, {'id':3,'name':'Bee'}]

    def ordered(self,mode='alphabetical'):
        return [i['id'] for i in self.history.ordered(self.items,lambda i:i['name'],'client',42,7,mode)]

    def test_default_is_case_insensitive_alphabetical_even_with_history(self):
        self.history.remember('client',1,42,7)
        self.assertEqual(self.ordered(),[2,3,1])

    def test_recent_order_survives_new_history_instance(self):
        self.history.remember('client',3,42,7)
        self.history.remember('client',1,42,7)
        self.history=ChoiceHistory(self.vault)
        self.assertEqual(self.ordered('recent'),[1,3,2])
        self.assertEqual(self.history.selected(self.items,'client',42,7),'1')

    def test_account_business_and_dropdown_history_are_isolated(self):
        self.history.remember('client',1,42,7)
        for kind,identity,business in [('project',42,7),('client',43,7),('client',42,8)]:
            self.assertEqual(self.history.recent(kind,identity,business),[])

    def test_unavailable_selection_falls_back_to_valid_item(self):
        self.history.remember('client',99,42,7)
        items=self.history.ordered(self.items,lambda i:i['name'],'client',42,7)
        self.assertEqual(self.history.selected(items,'client',42,7),'2')
        self.assertEqual(self.history.selected([],'client',42,7),'')

    def test_history_is_deduplicated_and_bounded(self):
        for number in range(100):self.history.remember('client',str(number),42,7)
        self.history.remember('client',90,42,7)
        values=self.history.recent('client',42,7)
        self.assertEqual(values[0],'90')
        self.assertEqual(len(values),64)
        self.assertEqual(len(set(values)),64)


if __name__=='__main__':unittest.main()
