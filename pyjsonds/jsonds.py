import re
import os
import json
import glob


class roiterator(object):
    def __init__(self, obj):
        self.obj = obj
        self.counter = obj._indices.__iter__()

    def __next__(self):
        return self.counter.__next__()


def is_primitive(x):
    return isinstance(x, (int, float, bool, str, type(None)))


def is_subset(mydata, other):
    return len([i for i in mydata if i not in other]) == 0


def is_equal_sets(mydata, other):
    return is_subset(mydata, other) and is_subset(other, mydata)


def set_diff(mydata, other, field):
    return len([i for i in mydata[field] if i not in other[field]]) > 0


def onlyprimitives(dlist):
    return False not in [is_primitive(x) for x in dlist]


class jsonds(object):
    def __init__(self, parent, data, uri, name, object_index, recurse,
                 context, collect):
        self._state_incr()
        self._parent = parent
        self._endpoint = parent._endpoint
        self._uri = uri
        self._data = data
        self._name = name
        self._entrylist = []
        self._indices = []
        self._AllowNumerical_Index = False
        self._todo = []
        self._object_index = object_index
        self._schemas = parent._schemas
        #print("Getting {0}.{1}".format(self._uri, ("" if self._name is None
        #                                           else self._name)))
        self._collector = (self._parent._collector if self._parent is not None
                           else {})
        if collect is None:
            collect = collectupdates()
        if object_index in self._collector:
            print("************** Why is it already there?")
        self._collector[object_index] = self
        self._do_refresh(context, data, recurse, 'Constructor', None, collect)
        self._state_decr()

    def _state_incr(self):
        if ('_state' not in self.__dict__):
            self.__dict__['_state'] = state()
        self.__dict__['_state'].incr()

    def _state_decr(self):
        if '_state' in self.__dict__:
            self.__dict__['_state'].decr()

    def __iter__(self):
        if (self._spec is not None and 'type' in self._spec.spec and
                self._spec.spec['type'] != 'array'):
            raise AttributeError("Not iterable")
        if len(self._todo):
            self.refresh(True)
        return roiterator(self)

    def __getattr__(self, name):
        if name.startswith('_'):
            return self.__dict__[name] if name in self.__dict__ else None
        if name in self._todo:
            self._do_refresh('Create', self._data, 1, 'Get', [name],
                             collectupdates())
        if name in self.__dict__:
            return self.__dict__[name]
        if self._spec is None or ('properties' in self._spec.spec and
                                  name in self._spec.spec['properties']):
            return None
        raise AttributeError('Invalid attribute ' + name)

    def __setattr__(self, name, value):
        if name == "Actions":
            return
        if self.__dict__['_state'].is_creating() or name.startswith('_'):
            self.__dict__[name] = value
            return
        nvalue = self.my_edit_value(name, value)
        if True or nvalue != self.__dict__[name]:
            payload = {name: value}
            # TODO
            if (self._parent._iseditable and
                    '@Redfish.SettingsApplyTime' in self._parent.__dict__):
                payload.update({'@Redfish.SettingsApplyTime': self._parent.
                                __dict__['@Redfish.SettingsApplyTime']})
            if (self._iseditable and
                    '@Redfish.SettingsApplyTime' in self.__dict__):
                payload.update({'@Redfish.SettingsApplyTime': self.__dict__[
                                '@Redfish.SettingsApplyTime']})
            robj = self._endpoint.patch(etag(self.__dict__), self._uri,
                                        **payload)
            if robj._ResponseStatus:
                self.__dict__[name] = nvalue
            else:
                raise ValueError("Could not update: {0}={1}".
                                 format(name, value))

    def __len__(self):
        return len(self._indices)

    def __getitem__(self, key):
        if (len(self._indices) == 0 and len(self._todo) > 0 and
                isinstance(key, int) and
                not isinstance(self._todo[0], int)):
            self._AllowNumerical_Index = True

        if isinstance(key, int) and self._AllowNumerical_Index:
            idx = (key-1 if key >= 1 else key)
            if idx < len(self._indices):
                key = self._indices[idx]
            elif idx < len(self._data):
                key = self._todo[idx-len(self._indices)]
                keys = self._todo[0:idx-len(self._indices)+1]
                self._do_refresh('Create', self._data, 1, 'Get', keys,
                                 collectupdates())
        elif key in self._todo:
            self._do_refresh('Create', self._data, 1, 'Get', [key],
                             collectupdates())
        return self._entrylist[self._indices.index(key)]

    def __setitem__(self, key, value):
        if (len(self._entrylist) > 0 and
                not isinstance(self._entrylist[0], int)):
            self._AllowNumerical_Index = True
            idx = None
        if self._AllowNumerical_Index and isinstance(key, int):
            idx = (key-1 if key >= 1 else key)
        if idx is None:
            idx = self._indices.index(key)
        if self.__dict__['_state'].is_creating():
            self._entrylist[idx] = value
        else:
            # TODO: Don't allow overwrites. will cause references to be lost
            nvalue = self.my_allow_add(key, value)

    def __delitem__(self, key):
        if self.__dict__['_state'].is_creating():
            del self._indices[idx]
            del self._entrylist[idx]
        self.my_allow_del(key)

    def refresh(self, fetchall=False, **kwargs):
        # refreshes immediate object!
        collector = collectupdates()
        collector.seen[self._uri] = True
        self._do_refresh('Create', self._data, 1, 'Refresh',
                         self.fields() if not fetchall else None,
                         collector, **kwargs)
        return self

    def fields(self):
        return [i for i in self.__dict__
                if not i.startswith('_') and
                not isinstance(self.__dict__[i], roobject)]

    def value(self, field):
        return self.__dict__[field]

    def __contains__(self, value):
        return False

    def my_before(self, object_index, value):
        pass

    def my_edit_value(self, name, value):
        raise AttributeError("Cannot modify object")

    def my_allow_add(self, key, value):
        raise AttributeError("Cannot modify object")

    def my_allow_del(self, key):
        raise AttributeError("Cannot modify object")

    def has_member(self, member_name):
        return member_name in self.__dict__

    def __str__(self):
        s = []
        separator = ", "
        fields = dict((i, self.__dict__[i]) for i in self.__dict__
                      if not i.startswith('_') and
                      not callable(self.__dict__[i]))
        for i in fields:
            if is_primitive(self.__dict__[i]):
                s.append(i + "=" + str(self.__dict__[i]))
            else:
                s.append(i + "=[" + str(self.__dict__[i]) + ']')
                separator = "\n"
        return separator.join(s)

    @property
    def Indices(self):
        return list(self._indices)

    def getit(self, *args):
        obj = self
        for i in args:
            if i not in obj.__dict__:
                return None
            obj = obj.__dict__[i]
        return obj

    @property
    def Redfish_Settings(self):
        if self.has_member('@Redfish.Settings'):
            self.getit('@Redfish.Settings').SettingsObject._iseditable = True
            return self.getit('@Redfish.Settings').SettingsObject
        return None

    def as_json(self):
        gfields = sorted([i for i in self.__dict__.keys()
                          if not i.startswith('_')])
        return dict(zip(gfields, map(lambda x: (self.__dict__[x].as_json()
                    if isinstance(self.__dict__[x], roobject) else
                    self.__dict__[x]), gfields)))

    # none = all
    # only = only
    # exclude = all-exclude
    # only, exclude = only-exclude
    # exclude, include = all-exclude+include
    # include = error
    # only, include = error
    # only, exclude, include = only-exclude+include

    def Properties(self, only=[], exclude=[], include=[], no_prefix=True):
        if len(exclude) == 0 and len(include) != 0:
            print("WARNING: include cannot be provided without exclude")
            include = []
        # print("==== only= {0}\n===== exclude={1}\n======include={2}".
        #       format(only, exclude, include))
        return self._properties("", {}, only, exclude, include, no_prefix)

    def _properties(self, prefix, entry, only, exclude, include, no_prefix):
        short_list = [(prefix + i, i) for i in self.__dict__
                      if not i.startswith('_') and
                      not i.startswith('@') and
                      not callable(self.__dict__[i]) and
                      not isinstance(self.__dict__[i], roobject)]

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
        children = [i for i in self.__dict__
                    if not i.startswith('_') and
                    not i.startswith('@') and
                    not callable(self.__dict__[i]) and
                    isinstance(self.__dict__[i], roobject)]
        for i in children:
            self.__dict__[i]._properties(i + "." if prefix == ""
                                         else prefix + i + ".", entry, only,
                                         exclude, include, no_prefix)
        return entry

    def _do_refresh(self, context, mydata, recurse, gcontext, fields,
                    collect, **condition):

        # condition can contain '$skip': count
        if gcontext in ['Refresh', 'Constructor']:
            self._data = (mydata if self._data is not None and
                          self._uri == self._parent._uri
                          else self._endpoint.get(self._name, self._uri, True,
                                                  **condition))
            mydata = self._data

        if mydata is None or len(mydata) == 0:
            return

        if gcontext in ['Constructor']:
            self.my_before(self._object_index, context)

        collect.set_context(self._uri)

        if isinstance(mydata, dict):
            for field in mydata:
                # ignore special handling fields or if not in fields
                if (field in ['_version', '_index'] or
                        (fields is not None and field not in fields)):
                    continue

                # primitive or ODATA fields, simply carry over
                if '@odata.' in field or is_primitive(mydata[field]):
                    if gcontext in ['User']:
                        nvalue = self.my_edit_value(field, mydata[field])
                    else:
                        nvalue = mydata[field]

                    if (field not in self.__dict__ or
                            self.__dict__[field] != nvalue):
                        # apply value if created or modified
                        self.__dict__[field] = nvalue
                        # track this value for updates
                        collect.set(field, nvalue)
                    continue

                # list of primitives, process here
                if (isinstance(mydata[field], list) and
                        onlyprimitives(mydata[field])):
                    if gcontext in ['User']:
                        nvalue = self.my_edit_value(field, mydata[field])
                    else:
                        nvalue = mydata[field]

                    if (field not in self.__dict__ or
                        not is_equal_sets(mydata[field],
                                          self.__dict__[field])):
                        # apply value if created or modified
                        self.__dict__[field] = nvalue
                        # track this value for updates
                        collect.set(field, nvalue)
                    continue

                # index of the child object
                object_index = None

                # external reference:
                if (isinstance(mydata[field], dict) and
                        len(mydata[field]) == 1 and
                        '@odata.id' in mydata[field]):
                    # mydata refers to external link. '@odata.id' is the URI.
                    if recurse <= 0:
                        # if asked to stop recursion, put it into _todo list
                        if field not in self._todo:
                            self._todo.append(field)
                        continue
                    # object_index points to child_index
                    object_index = mydata[field]['@odata.id']
                    (item_data, item_uri) = (None, mydata[field]['@odata.id'])

                # struct or list of structs
                if object_index is None:
                    # object_index points to child_index = uri + name
                    # it is simply struct. Use existing data, item_uri is uri
                    object_index = "/".join([str(ent) for ent in [
                                             self._parent._object_index,
                                             self._name, field] if ent])
                    object_index = object_index.replace("//", "/")
                    (item_data, item_uri) = (mydata[field], self._uri)

                # start the updates
                if field in self._todo:
                    self._todo.remove(field)
                collect.set(field, {})
                next_recurse = recurse-1 if item_uri != self._uri else recurse
                if object_index not in self._collector:
                    self.__dict__[field] = type(self)(self, item_data,
                                                      item_uri, field,
                                                      object_index,
                                                      next_recurse,
                                                      context, collect)
                else:
                    if (field not in self.__dict__ or
                            self.__dict__[field] !=
                            self._collector[object_index]):
                        self.__dict__[field] = self._collector[object_index]
                    if object_index not in collect.seen:
                        collect.seen[object_index] = True
                        self._collector[object_index]._do_refresh(context,
                                                                  item_data,
                                                                  next_recurse,
                                                                  gcontext,
                                                                  None,
                                                                  collect)
                collect.oldstate()

        if isinstance(mydata, list):
            counter = len(self._indices)-1
            for entry in mydata:
                counter += 1

                object_index = None
                # ext ref, internal struct

                # External reference
                if (isinstance(entry, dict) and len(entry) == 1 and
                        '@odata.id' in entry):
                    # mydata refers to external link. '@odata.id' is the URI.
                    # object_index points to child_index
                    object_index = entry['@odata.id']
                    mydata = None

                # User creating external ref
                if gcontext in ['User'] and '_version' in entry:
                    if entry['_version'] == "similar":
                        if len(self._indices) == 0:
                            raise ValueError('no similar entries found')
                        for i in [j for j in self._entrylist[0].__dict__
                                  if j.startswith("@odata")]:
                            entry[i] = self._entrylist[0].__dict__[i]
                    else:
                        version = 'latest'
                        if '_version' in entry:
                            version = entry['_version']
                            del entry['_version']
                        item_ref = self._spec.spec['items']['$ref']
                        spec1 = self._schemas.resolve_ref(self._spec,
                                                          item_ref,
                                                          entry, 'Create',
                                                          version)
                        version = os.path.basename(spec1.fname)
                        version = version.replace('.json', '')
                        clsname = version.split('.')[0]
                        entry['@odata.type'] = \
                            "# {1}.{0}".format(clsname, version)

                    item_index = (entry['_index'] if '_index' in entry
                                  else counter)
                    sitem = [str(ent) for ent in [self._uri, item_index]
                             if ent]
                    entry['@odata.id'] = "/".join(sitem).replace("//", "/")
                    object_index = entry['@odata.id']
                    mydata = entry

                if object_index is not None:
                    nidx = self._schemas.extract_index(entry['@odata.id'],
                                                       counter)
                    (item_data, item_uri, item_index) = (mydata,
                                                         entry['@odata.id'],
                                                         nidx)
                    if item_index is None:
                        # null entry!!
                        self._indices.append(counter)
                        self._entrylist.append(None)
                        continue
                    if not isinstance(item_index, int):
                        self._AllowNumerical_Index = True
                    if recurse <= 0:
                        # if asked to stop recursion, put it into _todo list
                        if item_index not in self._todo:
                            self._todo.append(item_index)
                        continue
                else:
                    (item_data, item_uri) = (entry, self._uri)
                    item_index = (entry['_index'] if '_index' in entry
                                  else counter)
                    object_index = "/".join([str(ent) for ent in [
                                             self._parent._object_index,
                                             self._name, item_index]
                                             if ent is not None])
                    object_index = object_index.replace("//", "/")

                # list of structs
                if fields is not None and item_index not in fields:
                    continue
                if item_index in self._todo:
                    self._todo.remove(item_index)

                collect.set_context(item_uri,
                                    object_index not in self._collector)
                next_recurse = (recurse-1 if item_uri != self._uri
                                else recurse)
                if object_index not in self._collector:
                    type(self)(self, item_data, item_uri, item_index,
                               object_index, next_recurse, context, collect)
                elif object_index not in collect.seen:
                    if isinstance(self._collector[object_index], list):
                        print("Not sure why I am here!")
                    else:
                        self._collector[object_index]._do_refresh(context,
                                                                  item_data,
                                                                  next_recurse,
                                                                  gcontext,
                                                                  None,
                                                                  collect)
                if item_index not in self._indices:
                    self._indices.append(item_index)
                    self._entrylist.append(self._collector[object_index])
                    collect.reuse_state()
                    collect.array_add(self._name, object_index)
            if (self._name + "@odata.count") in self._parent.__dict__:
                self._parent.__dict__[self._name + "@odata.count"] = len(self._indices)
                if collect is not None:
                    collect.array_entries(self._name, self._entrylist)


class coercable(roobject):
    def __init__(self, parent, data, uri, name, object_index, recurse,
                 context, collect):
        self._state_incr()
        super().__init__(parent, data, uri, name, object_index, recurse,
                         context, collect)
        self._state_decr()

    def my_before(self, object_index, context):
        tname = None if '@odata.type' in self._data else self._name
        self._spec = self._schemas.resolve_type(self._parent._spec,
                                                tname, object_index,
                                                self._data, 'properties',
                                                context, None)
        self._actions = {}
        if ('properties' in self._spec.spec and
                'Actions' in self._spec.spec['properties']):
            actions = self._schemas.resolve_type(self._spec, 'Actions',
                                                 object_index, self._data,
                                                 'properties', None, None)
            for i in actions.spec['properties']:
                if i == "Oem":
                    continue
                nactions = self._schemas.resolve_type(actions, i,
                                                      object_index,
                                                      self._data,
                                                      'properties',
                                                      None, None)
                params = {}
                params_order = []
                self._schemas.fix_parameters(nactions, i)
                for param in nactions.spec['parameters']:
                    params[param] = self._schemas.resolve_type(nactions,
                                                               param,
                                                               object_index,
                                                               None,
                                                               'parameters',
                                                               None, None)
                    params[param].make_parameter(param)
                    params_order.append(param)
                self._actions[i.split('.')[-1]] = [params, params_order, i, i]
                target = (self._data['Actions'][i]['target']
                          if 'Actions' in self._data and
                             i in self._data['Actions'] and
                             'target' in self._data['Actions'][i]
                             else i.split('.')[-1])
                self._make_method(i.split('.')[-1], target)
        self.build_oem_actions()

    def build_oem_actions(self):
        if self._name is None or isinstance(self._name, int):
            return
        name = (self._name if self._name != "Oem" else
                self._object_index.replace('/', '_').strip('_'))
        oemfile = os.path.join('..', 'oem', 'dell', 'json-schema',
                               name + ".json")
        oemspec = None
        for file in glob.glob(oemfile):
            with open(file) as f:
                oemspec = json.load(f)
            if '@odata.id' in oemspec and oemspec['@odata.id'] != self._uri:
                oemspec = None
        if oemspec is None:
            return
        if '_actions' not in self.__dict__:
            self._actions = {}
        if ('Actions' in oemspec):
            for i in oemspec['Actions']['properties']:
                object_index = self._object_index + "/" + i
                nactions = (self._schemas.resolve_oem_type(self._spec, i,
                            oemspec['Actions']['properties'][i], None))
                params = {}
                params_order = []
                if 'parameters' not in nactions.spec:
                    self._schemas.fix_parameters(nactions, i)
                for param in nactions.spec['parameters']:
                    params[param] = self._schemas.resolve_oem_type(
                        nactions, param, nactions.spec['parameters'][param], None)
                    params[param].make_parameter(param)
                    params_order.append(param)
                intref = oemspec['Actions']['properties'][i]['intref']
                self._actions[i.split('.')[-1]] = [params, params_order, i, intref]
                if 'Actions' in self._data and intref in self._data['Actions']:
                    target = self._data['Actions'][intref]['target']
                elif intref in self._data:
                    target = self._data[intref]['target']
                elif intref in self.__dict__:
                    target = self.__dict__[intref].target
                elif 'target' in nactions.spec:
                    target = nactions.spec['target']
                else:
                    target = None
                self._make_method(i.split('.')[-1], target)

    def _make_method(self, fname, target):
        def func1(*args, **kwargs):
            myname = func1.__name__
            return self.call(fname, target, *args, **kwargs)
        func1.__name__ = fname
        setattr(self, fname, func1)

    def call(self, fname, target, *args, **kwargs):
        skip = {'v1_4_0': ['ResetType']}
        args_values = {}
        for i in range(0, len(args)):
            if self._actions[fname][1][i] in kwargs:
                raise AttributeError(self._actions[fname][1][i] + " is both args and kwargs")
            kwargs[self._actions[fname][1][i]] = args[i]
        paramsets = {}
        for name in kwargs:
            if name not in self._actions[fname][0]:
                ver = os.path.basename(self._spec.fname).replace('.json', '').split('.')[1]
                if ver in skip and name in skip[ver]:
                    print("WARNING: skipping " + name)
                    continue
                raise AttributeError(name + " is not valid argument")
            value = kwargs[name]
            is_sanitized = False
            if (name + '@Redfish.AllowableValues') in self.__dict__:
                if value not in self.__dict__[name + '@Redfish.AllowableValues']:
                    raise ValueError(value + " is not allowed for " + name)
            elif (self._actions[fname][3] is not None and
                  'Actions' in self.__dict__ and
                  self._actions[fname][3] in self.Actions.__dict__):
                actref = self.Actions.__dict__[self._actions[fname][3]]
                if (name + '@Redfish.AllowableValues') in actref.__dict__:
                    if value not in actref.__dict__[name + '@Redfish.AllowableValues']:
                        raise ValueError(value + " is not allowed for " + name)
                    is_sanitized = True
            if not is_sanitized:
                value = self._actions[fname][0][name].sanitize_value(name, value)
            if 'paramset' in self._actions[fname][0][name].spec:
                if self._actions[fname][0][name].spec['paramset'] not in paramsets:
                    paramsets[self._actions[fname][0][name].spec['paramset']] = {}
                paramsets[self._actions[fname][0][name].spec['paramset']][name] = value
            if 'group' in self._actions[fname][0][name].spec:
                if self._actions[fname][0][name].spec['group'] not in args_values:
                    args_values[self._actions[fname][0][name].spec['group']] = {}
                args_values[self._actions[fname][0][name].spec['group']][name] = value
            else:
                args_values[name] = value
        for name in self._actions[fname][0]:
            if name not in kwargs and self._actions[fname][0][name].child_spec[name].Required:
                raise AttributeError(name + " is mandatory")
            if 'paramset' in self._actions[fname][0][name].spec:
                pset = self._actions[fname][0][name].spec['paramset']
                if pset in paramsets and name not in paramsets[pset]:
                    raise ValueError(name + " is needed for " + pset)
        if target is None and 'target' in self._data:
            target = self._data['target']
        return self._endpoint.action(etag(self.__dict__), target, **args_values)

    def get_allowed_values(self, fname, argname):
        skip = {'v1_4_0': ['ResetType']}
        if argname not in self._actions[fname][0]:
            ver = os.path.basename(self._spec.fname).replace('.json', '').split('.')[1]
            if ver in skip and argname in skip[ver]:
                print("WARNING: skipping " + argname)
                return []
            raise AttributeError(argname + " is not valid argument")
        if (argname + '@Redfish.AllowableValues') in self.__dict__:
            return self.__dict__[argname + '@Redfish.AllowableValues']
        elif (self._actions[fname][3] is not None and
                'Actions' in self.__dict__ and
                self._actions[fname][3] in self.Actions.__dict__):
            actref = self.Actions.__dict__[self._actions[fname][3]]
            if (argname + '@Redfish.AllowableValues') in actref.__dict__:
                return actref.__dict__[argname + '@Redfish.AllowableValues']
        return self._actions[fname][0][name].child_spec[name].AllowedValues

# Cooerceable


class cuiterator(object):
    def __init__(self, obj):
        self.obj = obj
        self.counter = range(len(obj.uris)-1, -1, -1).__iter__()

    def __next__(self):
        return self.obj.uris[self.counter.__next__()]


class collectupdates:
    def __init__(self):
        self.updates = {}
        self.uris = []
        self.oldstates = []
        self.curstate = None
        self.types = {}
        self.seen = {}

    def set_context(self, uri, newobject=False):
        if uri not in self.updates:
            self.updates[uri] = {}
            self.curstate = self.updates[uri]
            self.uri = uri
            self.oldstates.append((uri, self.curstate))
            self.uris.append(uri)
            self.types[uri] = newobject

    def set(self, field, value):
        self.curstate[field] = value
        if isinstance(value, dict):
            self.oldstates.append((self.uri, self.curstate))
            self.curstate = value

    def array_add(self, field, value):
        pass

    def array_entries(self, field, entrylist):
        self.curstate[field] = []
        for i in entrylist:
            self.curstate[field].append({'@odata.id': i._uri})
        self.curstate[field + "@odata.count"] = len(entrylist)

    def array_delete(self, field, value):
        pass

    def oldstate(self):
        (self.uri, self.curstate) = self.oldstates[-1]
        del self.oldstates[-1]

    def reuse_state(self):
        (self.uri, self.curstate) = self.oldstates[-1]

    def __iter__(self):
        return cuiterator(self)


class editable(coercable):
    def __init__(self, parent, data, uri, name, object_index, recurse, context, collect):
        self._state_incr()
        super().__init__(parent, data, uri, name, object_index, recurse, context, collect)
        self._state_decr()

    def my_edit_value(self, name, value):
        if self._parent._iseditable:
            return value
        allow_edit = not self._spec.IsReadOnly(name)
        if name not in self.__dict__ and not name.startswith('_'):
            if name not in self._spec.spec['properties']:
                raise AttributeError('Invalid attribute (1)' + name)
            allow_edit = True
        if not allow_edit:
            raise AttributeError(" {0} is readonly attribute".format(name))
        if (name + '@Redfish.AllowableValues') in self.__dict__:
            if value not in self.__dict__[name + '@Redfish.AllowableValues']:
                raise ValueError(value + " is not allowed for " + name)
            return value
        nvalue = self._spec.sanitize_value(name, value)
        return nvalue

    def upsert(self, data):
        collect = collectupdates()
        self._do_refresh('Create', data, 10, 'User', None, collect)
        for uri in collect:
            if collect.types[uri]:
                robj = self._endpoint.update(etag(self.__dict__), uri, **collect.updates[uri])
                if not robj._ResponseStatus:
                    print("Failed in setting the changes")
                    raise ValueError(robj)

        for uri in collect:
            if not collect.types[uri]:
                robj = self._endpoint.patch(etag(self.__dict__), uri, **collect.updates[uri])
                if not robj._ResponseStatus:
                    print("Failed in setting the changes")
                    raise ValueError(robj)

    def new(self, id, **kwargs):
        if 'items' not in self._spec.spec:
            raise AttributeError("Not supported")
        if id in self._indices:
            raise IndexError(str(id) + " is already present in indices")
        kwargs['_index'] = id
        self.upsert([kwargs])

    # Simple convenience using kwargs
    def update_fields(self, **kwargs):
        if self.__dict__['_state'].is_creating():
            for i in kwargs:
                self.__setattr__(i, kwargs[i])
        else:
            self.upsert(kwargs)

    def ApplyTimeSettings(self, **kwargs):
        self._iseditable = True
        self.__dict__["@Redfish.SettingsApplyTime"] = kwargs

    def find_first(self, **kwargs):
        for entry in self._entrylist:
            matches = not (False in [entry.__dict__[i] == kwargs[i]
                           for i in entry.__dict__ if i in kwargs])
            if matches:
                return entry
        return None

    def delete(self):
        if not self._endpoint.delete(etag(self.__dict__), self._uri):
            raise AttributeError("Unable to delete entry")
        objs = [self.__dict__[entry] for entry in self.__dict__.keys()
                if isinstance(self.__dict__[entry], roobject) and
                self._uri == self.__dict__[entry]._uri]
        for entry in objs:
            del self._collector[entry._object_index]
        del self._collector[self._object_index]
        return True

    def my_allow_del(self, key):
        if not self._spec.deletable:
            raise AttributeError("This class does not allow deletion of entries")
        if self._AllowNumerical_Index and isinstance(key, int):
            idx = (key-1 if key >= 1 else key)
        else:
            idx = self._indices.index(key)
        if self._entrylist[idx].delete():
            del self._indices[idx]
            del self._entrylist[idx]
            if (self._name + "@odata.count") in self._parent.__dict__:
                self._parent.__dict__[self._name + "@odata.count"] = len(self._indices)
        else:
            raise AttributeError("Deletion of entry failed!")

