"""This file contains all the data structures used by Py3oConvertor
See the docstring of Py3oConvertor.__call__() for further information
"""
from numbers import Number


class Py3oDataError(Exception):
    pass


class Py3oObject(dict):
    """ Base class to be inherited.
    """
    def render(self, data):  # pragma: no cover
        raise NotImplementedError("This function should be overriden")

    def __repr__(self):  # pragma: no cover
        res = super(Py3oObject, self).__repr__()
        return "{}({})".format(
            self.__class__.__name__,
            res
        )

    def get_size(self):
        """Return the max depth of the object
        """
        sizes = [val.get_size() for val in self.values()]
        if not sizes:
            return 0
        return max(sizes) + 1

    def get_key(self):
        """Return the first key
        """
        return next(iter(self.keys()))

    def rupdate(self, other):
        """Update recursively the Py3oObject self with the Py3oObject other.
        Example:
        self = Py3oObject({
            'a': Py3oObject({}),
            'b': Py3oObject({
                'c': Py3oObject({}),
            }),
        })
        other = Py3oObject({
            'b': Py3oObject({
                'd': Py3oObject({}),
            }),
        })
        res = Py3oObject({
            'a': Py3oObject({}),
            'b': Py3oObject({
                'c': Py3oObject({}),
                'd': Py3oObject({}),
            }),
        })
        """
        for key, value in other.items():
            if key in self:
                self[key].rupdate(value)
            else:
                self[key] = value


class Py3oModule(Py3oObject):
    def render(self, data):
        """ This function will render the datastruct according
         to the user's data
        """
        res = {}
        for key, value in self.items():
            subdata = data.get(key, None)
            if subdata is None:
                raise Py3oDataError(
                    "The key '%s' must be present"
                    " in your data dictionary" % key
                )
            # Spread only the appropriate data to its children
            val = value.render(data.get(key))
            if val is not None:
                res[key] = val
        return res


class Py3oArray(Py3oObject):
    """ A class representing an array.
    The attribute direct_access will tell if this class should be considered
     as a list of dict or a list of values.
    """
    def __init__(self):
        super(Py3oArray, self).__init__()
        self.direct_access = False

    def render(self, data):
        """ This function will render the datastruct according
        to the user's data
        """
        if self.direct_access:
            return data
        if not self:
            return None
        res = []
        for d in data:
            tmp_dict = {}
            for key, value in self.items():
                # Spread only the appropriate data to its children
                tmp_dict[key] = value.render(getattr(d, key))
            res.append(tmp_dict)
        return res


class Py3oBuiltin(Py3oObject):
    """ This class holds information about builtins
    """
    pass


class Py3oName(Py3oObject):
    """ This class holds information of variables.
    Keys are attributes and values the type of this attribute
     (another Py3o class or a simple value)
    i.e.: i.egg -> Py3oName({'i': Py3oName({'egg': Py3oName({})})})
    """
    def render(self, data):
        """ This function will render the datastruct according
        to the user's data
        """
        if not self:
            # We only send False values if the value is a number
            # otherwise we convert the False into an empty string
            if isinstance(data, Number):
                return data
            return data or u""
        res = {}

        for key, value in self.items():
            # Spread only the appropriate data to its children
            res[key] = value.render(getattr(data, key))
        return res


class Py3oCall(Py3oObject):
    """This class holds information of function call.
    'name' holds the name of function as a Py3oName
    The keys are the arguments as:
        - numeric keys are positional arguments oredered ascendently
        - string keys are keywords arguments
    """
    def __init__(self, dict):
        super(Py3oCall, self).__init__(dict)
        self.name = None


class Py3oDummy(Py3oObject):
    """ This class holds temporary dict, or unused attribute
     such as counters from enumerate()
    """
    pass
