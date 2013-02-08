# coding: utf-8
"""
This interface provides a simple way to declare and store parameters
in Modoboa's database.

Core components or extensions can register their own parameters, which
will be available and modifiable directly from the web interface.

Only super users will be able to access this part of the web interface.
"""

import inspect
import re
import copy

_params = {}
_params_order = {}
_levels = {'A' : 'admin', 'U' : 'user'}

class NotDefined(Exception):
    def __init__(self, app, name):
        self.app = app
        self.name = name

    def __str__(self):
        return "Application '%s' and/or parameter '%s' not defined" \
            % (self.app, self.name)

def register_app(app=None, aparams_opts=None, uparams_opts=None):
    """Manually register an application

    You don't need to call this function unless you want to provide
    specific options for your application parameters.

    For example, you can indicate that user-level parameters are only
    accessible for users that own a mailbox.

    :param app: the application's name
    :param aparams_opts: a dict containing options applicable to admin-level params
    :param uparams_opts: a dict containing options applicable to user-level params
    """
    if app is None:
        app = __guess_extension()

    if _params.has_key(app):
        return
    _params[app] = {}
    _params[app]['options'] = {}
    _params_order[app] = {}
    for lvl in _levels.keys():
        _params[app][lvl] = {}
        _params_order[app][lvl] = []

    if aparams_opts:
        _params[app]['options']['A'] = aparams_opts
    if uparams_opts:
        _params[app]['options']['U'] = uparams_opts

def unregister_app(app):
    """Unregister an application

    All parameters associated to this application will also be
    removed.

    :param app: the application's name (string)
    """
    if not _params.has_key(app):
        return False
    del _params[app]
    return True

def __is_defined(app, level, name):
    if not level in _levels.keys() \
            or not app in _params.keys() \
            or not name in _params[app][level].keys():
        raise NotDefined(app, name)

def __register(app, level, name, **kwargs):
    """Register a new parameter.

    ``app`` corresponds to a core component (admin, main) or to an
    extension.

    :param name: the application's name
    :param level: the level this parameter is available from
    :param name: the parameter's name
    """
    if not app in _params.keys():
        register_app(app)

    if not level in _levels.keys():
        return
    if _params[app][level].has_key(name):
        return
    _params[app][level][name] = {}
    _params_order[app][level] += [name]
    for k, v in kwargs.iteritems():
        _params[app][level][name][k] = v

def __update(app, level, name, **kwargs):
    """Update a parameter's definition

    :param app: the application's name
    :param level: the level this parameter is available from
    :param name: the parameter's name
    """
    if not app in _params.keys() or not level in _levels.keys() \
            or not _params[app][level].has_key(name):
        return
    for k, v in kwargs.iteritems():
        _params[app][level][name][k] = v

def __guess_extension():
    """Tries to guess the application's name by inspecting the stack

    :return: a string or None
    """
    modname = inspect.getmodule(inspect.stack()[2][0]).__name__
    m = re.match("(?:modoboa\.)?(?:extensions\.)?([^\.$]+)", modname)
    if m:
        return m.group(1)
    return None

def register_admin(name, **kwargs):
    """Register a new parameter (admin level)

    Each parameter is associated to one application. If no application
    is provided, the function tries to guess the appropriate one.

    :param name: the parameter's name
    """
    if kwargs.has_key("app"):
        app = kwargs["app"]
        del kwargs["app"]
    else:
        app = __guess_extension()
    return __register(app, 'A', name, **kwargs)

def update_admin(name, **kwargs):
    """Update a parameter's definition (admin level)

    Each parameter is associated to one application. If no application
    is provided, the function tries to guess the appropriate one.

    :param name: the parameter's name
    """
    if kwargs.has_key("app"):
        app = kwargs["app"]
        del kwargs["app"]
    else:
        app = __guess_extension()
    return __update(app, 'A', name, **kwargs)

def register_user(name, **kwargs):
    """Register a new user-level parameter

    :param name: the parameter's name
    """
    if kwargs.has_key("app"):
        app = kwargs["app"]
        del kwargs["app"]
    else:
        app = __guess_extension()
    return __register(app, 'U', name, **kwargs)

def get_param_def(app, level, name):
    """Return the definition of a given parameter

    :param app: the application's name
    :param level: the required level (A or U)
    :param name: the parameter's name
    :return: a dictionnary
    """
    __is_defined(app, level, name)
    return _params[app][level][name]

def save_admin(name, value, app=None):
    from models import Parameter

    if app is None:
        app = __guess_extension()
    __is_defined(app, 'A', name)
    fullname = "%s.%s" % (app, name)
    try:
        p = Parameter.objects.get(name=fullname)
    except Parameter.DoesNotExist:
        p = Parameter()
        p.name = fullname
    if p.value != value:
        pdef = get_param_def(app, 'A', name)
        if "modify_cb" in pdef:
            pdef["modify_cb"](value)
        p.value = value.encode("unicode_escape").strip()
        p.save()
    return True

def save_user(user, name, value, app=None):
    from models import UserParameter

    if app is None:
        app = __guess_extension()
    __is_defined(app, 'U', name)
    fullname = "%s.%s" % (app, name)
    try:
        p = UserParameter.objects.get(user=user, name=fullname)
    except UserParameter.DoesNotExist:
        p = UserParameter()
        p.user = user
        p.name = fullname
    if p.value != value:
        pdef = get_param_def(app, 'U', name)
        if "modify_cb" in pdef:
            pdef["modify_cb"](value)
        p.value = value.encode("unicode_escape").strip()
        p.save()
    return True

def get_admin(name, app=None):
    from models import Parameter

    if app is None:
        app = __guess_extension()
    __is_defined(app, "A", name)
    try:
        p = Parameter.objects.get(name="%s.%s" % (app, name))
    except Parameter.DoesNotExist:
        return _params[app]["A"][name]["deflt"]
    return p.value.decode("unicode_escape")

def get_all_admin_parameters():
    """Retrieve all administrative parameters

    Returned parameters are sorted by application

    :return: a list of dictionaries
    """
    result = []
    for app in sorted(_params.keys()):
        tmp = {"name" : app, "params" : []}
        for p in _params_order[app]['A']:
            newdef = copy.deepcopy(_params[app]['A'][p])
            newdef["name"] = p
            newdef["value"] = get_admin(p, app=app)
            tmp["params"] += [newdef]
        result += [tmp]
    return result

def get_user(user, name, app=None):
    from models import UserParameter

    if app is None:
        app = __guess_extension()
    __is_defined(app, "U", name)
    try:
        p = UserParameter.objects.get(user=user, name="%s.%s" % (app, name))
    except UserParameter.DoesNotExist:
        return _params[app]["U"][name]["deflt"]
    return p.value.decode("unicode_escape")

def get_all_user_params(user):
    """Retrieve all the parameters of the given user

    Returned parameters are sorted by application.

    :param user: a ``User`` object
    :return: a list of dictionaries
    """
    result = []
    for app in sorted(_params.keys()):
        if not len(_params[app]['U']):
            continue
        if get_app_option('U', 'needs_mailbox', False, app=app) \
                and not user.has_mailbox:
            continue
        tmp = {"name" : app, "params" : []}
        for p in _params_order[app]['U']:
            param_def = _params[app]['U'][p]
            newdef = copy.deepcopy(param_def)
            newdef["name"] = p
            newdef["value"] = get_user(user, p, app=app)
            tmp["params"] += [newdef]
        result += [tmp]
    return result

def get_app_option(lvl, name, dflt, app=None):
    """Retrieve a specific option for a given application

    If the option is not found, a default value is returned.

    :param lvl: the option's level (U or A)
    :param name: the option's name
    :param dflt: the default value to return
    :param app: the application name
    :return: the option's value
    """
    if app is None:
        app = __guess_extension()
    if not lvl in _params[app]['options']:
        return dflt
    if not _params[app]['options'][lvl].has_key(name):
        return dflt
    return _params[app]['options'][lvl][name]
