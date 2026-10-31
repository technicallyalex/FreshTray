"""Bounded session-only API read cache; writes and identity changes invalidate it."""
from collections import OrderedDict
from copy import deepcopy
import threading
import time

class ReadCache:
    def __init__(self,backend):
        self.backend=backend;self.items=OrderedDict();self.lock=threading.RLock()
    def __getattr__(self,name):return getattr(self.backend,name)
    def clear(self,kind=None):
        with self.lock:
            for key in list(self.items):
                if kind is None or key[0]==kind:del self.items[key]
    def read(self,key,work,ttl):
        with self.lock:
            cached=self.items.get(key)
            if cached and cached[0]>time.monotonic():
                self.items.move_to_end(key);return deepcopy(cached[1])
        result=work()
        with self.lock:
            self.items[key]=(time.monotonic()+ttl,deepcopy(result))
            while len(self.items)>32:self.items.popitem(last=False)
        return result
    def peek_month(self,business,month,identity):
        key=('month',str(business),month.isoformat(),str(identity))
        with self.lock:
            cached=self.items.get(key)
            if cached and cached[0]>time.monotonic():
                self.items.move_to_end(key);return deepcopy(cached[1])
        return None
    def profile(self):return self.read(('profile',),self.backend.profile,600)
    def catalog(self,business):return self.read(('catalog',str(business['id']),str(business.get('account_id'))),lambda:self.backend.catalog(business),600)
    def entries_for_month(self,business,month,identity):
        return self.read(('month',str(business),month.isoformat(),str(identity)),lambda:self.backend.entries_for_month(business,month,identity),300)
    def submit(self,*args):
        self.clear('month');return self.backend.submit(*args)
    def update_entry(self,*args):
        self.clear('month');return self.backend.update_entry(*args)
    def delete_entry(self,*args):
        self.clear('month');return self.backend.delete_entry(*args)
    def check_pending(self):
        self.clear('month');return self.backend.check_pending()
    def connect(self,*args):
        self.clear();return self.backend.connect(*args)
    def disconnect(self):
        self.clear();return self.backend.disconnect()
