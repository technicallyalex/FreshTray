"""Private, bounded selection history shared by dropdowns across restarts."""
from copy import deepcopy
import unicodedata


def item_id(item):
    return str(item.get('id', item.get('userid', '')))


class ChoiceHistory:
    def __init__(self, vault):
        self.vault = vault

    @staticmethod
    def key(kind, identity, business=''):
        return f'{identity}/{business}/{kind}'

    def recent(self, kind, identity, business=''):
        data = self.vault.get('ui_choices') or {}
        return data.get(self.key(kind, identity, business), [])

    def remember(self, kind, value, identity, business=''):
        if not value or identity is None:
            return
        key, value = self.key(kind, identity, business), str(value)
        data = deepcopy(self.vault.get('ui_choices') or {})
        old = data.get(key, [])
        if old and old[0] == value:
            return
        data.pop(key, None)
        data[key] = ([value] + [previous for previous in old if previous != value])[:64]
        while len(data) > 128:
            del data[next(iter(data))]
        # IDs and usage history belong in the encrypted vault, not settings/repo.
        self.vault.update(ui_choices=data)

    def ordered(self, items, name, kind, identity, business='', mode='alphabetical'):
        recent = self.recent(kind, identity, business) if mode == 'recent' else []
        ranks = {value: index for index, value in enumerate(recent)}
        def key(item):
            label = unicodedata.normalize('NFKD', name(item).strip()).casefold()
            return ranks.get(item_id(item), len(ranks)), label, item_id(item)
        return sorted(items, key=key)

    def selected(self, items, kind, identity, business=''):
        available = {item_id(item) for item in items}
        return next((value for value in self.recent(kind, identity, business) if value in available),
                    item_id(items[0]) if items else '')
