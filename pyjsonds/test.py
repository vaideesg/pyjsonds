#from jsonds import jsonds

isprim = lambda x: isinstance(x, (int, float, bool, str, type(None)))

class dsiter(object):
    def __init__(self, dsobj):
        self.dsobj = dsobj
        self.counter = dsobj._indices.__iter__()

    def __next__(self):
        return self.counter.__next__()

class jsonds():

    def __getitem__(self, key):
        if len(self._indices) == 0:
            raise IndexError(str(key) + " is not found")
        return self._entry[key]

    def __setitem__(self, key, value):
        if key not in self._indices:
            raise IndexError(str(key) + " is not found")

        if isinstance(value, jsonds):
            self.entry[key] = value
        else:
            self._init(entry[key], value)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            self.__dict__[name] = value
        elif name not in self.__dict__:
            raise AttributeError(str(name) + " is not found")
        elif value is None:
            self.__dict__[name] = None
        elif isinstance(value, jsonds) or isprim(value):
            self.__dict__[name] = value
        else:
            if name not in self.__dict__ or self.__dict__[name] == None:
                self.__dict__[name] = jsonds({})
            self._init(self.__dict__[name], value)

    def __repr__(self):
        return self._value

    def __str__(self):
        return str(self._value)

    def __iter__(self):
        return dsiter(self)

    # none = all
    # only = only
    # exclude = all-exclude
    # only, exclude = only-exclude
    # exclude, include = all-exclude+include
    # only, exclude, include = only-exclude+include

    # include = error
    # only, include = error

    # TODO
    def Properties(self, only=[], exclude=[], include=[], no_prefix=True):
        if len(exclude) == 0 and len(include) != 0:
            print("WARNING: include cannot be provided without exclude")
            include = []
        # print("==== only= {0}\n===== exclude={1}\n======include={2}".
        #       format(only, exclude, include))
        return self._properties("", {}, only, exclude, include, no_prefix)

    # TODO
    def _properties(self, prefix, entry, only, exclude, include, no_prefix):
        short_list = [(prefix + i, i) for i in self.__dict__
                      if not i.startswith('_') and
                      not i.startswith('@') and
                      not callable(self.__dict__[i]) and
                      not isinstance(self.__dict__[i], jsonds)]

        if len(only) != 0:
            short_list = [(a, b) for s in only for (a, b) in short_list
                          if a == s or a.startswith(s)]
        if len(exclude) != 0:
            excl_list = [(a, b) for s in exclude for (a, b) in short_list
                         if a == s or a.startswith(s)]
            excl_obj = [a for (a, b) in excl_list]
            short_list = [(a, b) for (a, b) in short_list
                          if a not in excl_obj]
        if len(include) != 0:
            short_list.extend([(a, b) for s in include for (a, b)
                               in excl_list if a == s or a.startswith(s)])
        entry.update(dict(zip(map(lambda x: x[1] if no_prefix and
                                  x[1] not in entry else x[0], short_list),
                     map(lambda x: self.__dict__[x[1]], short_list))))

        if True:
            children = [i for i in self.__dict__
                    if not i.startswith('_') and
                    not i.startswith('@') and
                    not callable(self.__dict__[i]) and
                    isinstance(self.__dict__[i], jsonds)]
            for i in children:
                self.__dict__[i]._properties(i + "." if prefix == ""
                                         else prefix + i + ".", entry, only,
                                         exclude, include, no_prefix)
        return entry

    def _init(self, obj, data):
        if isinstance(data, dict):
            for i in data:
                if isprim(data[i]):
                    obj.__dict__[i] = data[i]
                else:
                    obj.__dict__[i] = jsonds(data[i])
        elif isinstance(data, list):
            for i in data:
                if isprim(i):
                    obj._entry.append(i)
                    obj._indices.append(len(obj._entry)-1)
                else:
                    obj._entry.append(jsonds(i))
                    obj._indices.append(len(obj._entry)-1)
        else:
            obj._value = data

    def __init__(self, data):
        self._data = data
        self._entry = []
        self._indices = []
        self._init(self, data)

obj = jsonds({
    'a' : 'b',
    'c' : None,
    'dx' : True,
    'e' : [
        'j',
        'h',
        'i'
    ],
    't' : {
        'y' : 'h',
        'k' : 'y',
        'z' : 'y',
    }
})
print(obj.a)
print(obj.c)
print(obj.dx)
print([obj.e[i] for i in obj.e])
print([i for i in obj.e])
print(obj.t.y)
print(obj.t.k)
print(obj.Properties(only=['t.y'], no_prefix=False))
print(obj.Properties(exclude=['t.y'], no_prefix=False))
print(obj.Properties(exclude=['t'], include=['t.y'], no_prefix=False))

print(obj.Properties(only=['t'], no_prefix=False))
obj.t = { 'f' : 'c' }
print(obj.Properties(only=['t'], no_prefix=False))
obj.t = None
print(obj.Properties(only=['t'], no_prefix=False))
obj.t = { 'f' : 'c' }
print(obj.Properties(only=['t'], no_prefix=False))
print(jsonds(1))
