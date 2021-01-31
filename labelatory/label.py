
class Label():
    def __init__(self, name, color, description):
        self.name = name
        self._old_name = name
        self.color = color
        self.description = description

    @classmethod
    def load(cls, cfg_labels):
        pass

class Violation():
    """ Holds the violation. Can be color, description or name """
    def __init__(self, type, label, found=None, required=None):
        self.label = label
        self.type = type
        self.required = required
        self.found = found