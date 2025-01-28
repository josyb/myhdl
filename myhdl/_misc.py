#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2008 Jan Decaluwe
#
#  The myhdl library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public License as
#  published by the Free Software Foundation; either version 2.1 of the
#  License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

""" MyHDL miscellaneous public objects.

This module provides the following public myhdl objects:
instances -- function that returns instances in a generator function
downrange -- function that returns a downward range

"""
import inspect

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl import HdlClassInstanceError
from myhdl._Cosimulation import Cosimulation
from myhdl._instance import _Instantiator


def _isGenSeq(obj):
    from myhdl._block import _Block

    if isinstance(obj, (Cosimulation, _Instantiator, _Block)):
        return True

    if not isinstance(obj, (list, tuple, set)):
        return False

    for e in obj:
        if not _isGenSeq(e):
            return False

    return True


ismethod = inspect.ismethod
# inspect doc is wrong: ismethod checks both bound and unbound methods


def isboundmethod(m):
    return ismethod(m) and m.__self__ is not None


def instances():
    from myhdl._hdlclass import HdlClass
    from myhdl._block import _Block

    f = inspect.currentframe()
    # ic(f)
    of = inspect.getouterframes(f)
    # ic(of)
    d = of[1][0].f_locals
    l = []
    for k, v in d.items():
        # if hasattr(v, '__dict__'):
        #     ic(k, v, vars(v), isinstance(v, HdlClass))
        # else:
        #     ic(k, v)

        if _isGenSeq(v):
            l.append(v)

        elif isinstance(v, HdlClass):
            if k != 'self':
                thdl = v.hdl()
                if isinstance(thdl, _Block):
                    # it should be ...
                    thdl.name = k
                    thdl.modctxt = True  # TODO: ???
                    l.append(thdl)
                    # ic(k, v, thdl, vars(thdl))

                else:
                    raise HdlClassInstanceError(f'HdlClass "{v.__class__.__name__}" is missing @block decorator')

        elif isinstance(v, (list, tuple)):
            # descend
            # ic('got list', v)
            # assuming that the list only contains one type of objects
            idx = 0
            for vv in v:
                if _isGenSeq(vv):
                    l.append(vv)

                elif isinstance(vv, HdlClass):
                    if k != 'self':
                        thdl = vv.hdl()
                        if isinstance(thdl, _Block):
                            thdl.name = f'{k}{idx}'
                            idx += 1
                            thdl.modctxt = True  # TODO: ???
                            l.append(thdl)

                        else:
                            raise HdlClassInstanceError(f'HdlClass "{vv.__class__.__name__}" is missing @block decorator for `hdl` method')

    return l


def downrange(start, stop=0, step=1):
    """ Return a downward range. """
    return range(start - 1, stop - 1, -step)


def updatesymdict(sd, d):
    from myhdl._Signal import _Signal
    from myhdl._block import _Block
    from myhdl._intbv import intbv

    if 0:
        # ic(d)
        for k, v in d.items():
            # TODO: we will need objects for the actual *anonymous* `interface` and `ListOfSignals` object
            # as well for future true `Structure`, `Interface` and `Array` which in turn
            # will deprecate these two anonymous object, and **very** probably *ban* them?
            # and then breaking code Josy? Fui!
            if isinstance(v, (int, float, _Signal, intbv, _Block, _Instantiator)):
                if k in sd:
                    if id(v) != id(sd[k]):
                        raise KeyError(f'Key {k}:{sd[k]} already in symdict <> {k}:{v}')
                    else:
                        # is OK
                        pass
                else:
                    sd[k] = v
            elif isinstance(v, dict) and k == 'd':
                # an HdlClass 'hides' the arguments in key 'd' ...
                # yes, simply recurse
                updatesymdict(sd, v)
    else:
        sd.update(d)
    # ic(sd)
    return sd


def getsymdict(d):
    return updatesymdict({}, d)

