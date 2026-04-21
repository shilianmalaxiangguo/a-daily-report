HOOKS = {}


def register(name, fn):
    HOOKS[name] = fn


def resolve(name):
    return HOOKS[name]
