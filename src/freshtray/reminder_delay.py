"""Persistent one-shot reminder delay, independent of the daily schedule."""
from datetime import datetime, timedelta, timezone

def delay_minutes(value):
    try:
        minutes=int(value)
        if isinstance(value,bool) or float(value)!=minutes or not 1<=minutes<=1440:
            raise ValueError()
    except (TypeError,ValueError,OverflowError):
        raise ValueError('Enter a reminder delay from 1 to 1440 minutes.') from None
    return minutes

class ReminderDelay:
    def __init__(self,prefs,now=None):
        self.prefs=prefs;self.now=now or (lambda:datetime.now(timezone.utc));self.delivered=None
    def schedule(self,minutes):
        due=self.now()+timedelta(minutes=delay_minutes(minutes))
        self.prefs.save(reminder_again_at=due.isoformat());self.delivered=None
    def remaining(self):
        raw=self.prefs.data.get('reminder_again_at')
        if not raw or raw==self.delivered:return None
        try:
            due=datetime.fromisoformat(raw)
            if due.tzinfo is None:return None
            return max(0,(due-self.now()).total_seconds())
        except (TypeError,ValueError):return None
    def consume(self):
        if self.remaining()!=0:return False
        self.delivered=self.prefs.data['reminder_again_at']
        try:self.prefs.save(reminder_again_at=None)
        except OSError:pass  # Still deliver once in this process if storage is unavailable.
        return True
