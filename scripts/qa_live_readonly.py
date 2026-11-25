"""Verify that live QA rejects writes before calling the network transport."""
from unittest.mock import patch
from freshtray.live_readonly import LiveReadOnlyTransport
from freshtray.api import ApiError, Transport

t = LiveReadOnlyTransport()
with patch.object(Transport, '__call__', side_effect=AssertionError('Network reached')):
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        try:
            t(method, '/auth/oauth/token')
        except ApiError as exc:
            assert exc.status == 403
        else:
            raise AssertionError(method)
assert t.summary()['blocked_writes'] == 4
assert not t.events
print('PASS: write methods blocked before transport, including token refresh')
