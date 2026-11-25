"""Read-only live QA transport. Never logs URLs, headers, tokens or payloads."""
import time
import threading
from .api import Transport,ApiError

class LiveReadOnlyTransport(Transport):
    def __init__(self):super().__init__();self.events=[];self.blocked=0;self.guard=threading.Lock()
    def family(self,path):
        for needle,name in [('/users/me','profile'),('/invoices/invoices','invoices'),('/time_entries','time_entries'),('/users/clients','clients'),('/services','services'),('/projects','projects'),('/items/items','items'),('/systems/systems','business'),('/expenses/expenses','expenses')]:
            if needle in path:return name
        if '/estimates/estimates' in path:return 'estimates'
        if '/payments/payments' in path:return 'payments'
        return 'other'
    def __call__(self,method,path,body=None,token=None):
        if method not in ('GET','HEAD'):
            self.blocked+=1
            raise ApiError('Live QA blocks all write requests and token refreshes.',403)
        start=time.monotonic();status=200
        try:return super().__call__(method,path,body,token)
        except ApiError as exc:status=exc.status or 0;raise
        finally:
            with self.guard:self.events.append(dict(family=self.family(path),status=status,seconds=round(time.monotonic()-start,3)))
    def image(self,path,token):
        start=time.monotonic();status=200
        try:return super().image(path,token)
        except ApiError:status=0;raise
        finally:
            with self.guard:self.events.append(dict(family='images',status=status,seconds=round(time.monotonic()-start,3)))
    def summary(self):
        with self.guard:events=list(self.events)
        return dict(successful_gets={key:sum(e['status']==200 and e['family']==key for e in events) for key in sorted({e['family'] for e in events})},errors=[e for e in events if e['status']!=200],blocked_writes=self.blocked)
