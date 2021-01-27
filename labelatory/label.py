
class Label():
    def __init__(self, name, color, description):
        self.name = name
        self._old_name = name
        self.color = color
        self.description = description

    @classmethod
    def load(cls, cfg_labels):
        pass