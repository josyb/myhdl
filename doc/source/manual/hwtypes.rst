.. currentmodule:: myhdl

.. testsetup:: *

   from myhdl import *

.. _hwtypes:

***********************
Hardware-oriented types
***********************

.. _hwtypes-intbv:

The :class:`intbv` class
========================

.. index:: single: intbv; basic usage

Hardware design involves dealing with bits and bit-oriented operations. The
standard Python type :class:`int` has most of the desired features, but lacks
support for indexing and slicing. For this reason, MyHDL provides the
:class:`intbv` class. The name was chosen to suggest an integer with bit vector
flavor.

:class:`intbv` works transparently with other integer-like types. Like
class :class:`int`, it provides access to the underlying two's complement
representation for bitwise operations. However, unlike :class:`int`, it is
a mutable type. This means that its value can be changed after object
creation, through methods and operators such as slice assignment.

:class:`intbv` supports the same operators as :class:`int` for arithmetic. In
addition, it provides a number of features to make it suitable for hardware
design. First, the range of allowed values can be constrained. This makes it
possible to check the value at run time during simulation. Moreover, back end
tools can determine the smallest possible bit width for representing the object.
Secondly, it supports bit level operations by providing an indexing and slicing
interface.

:class:`intbv` objects are constructed in general as follows::

    intbv([val=None] [, min=None]  [, max=None])

*val* is the initial value. *min* and *max* can be used to constrain
the value. Following the Python conventions, *min* is inclusive, and
*max* is exclusive. Therefore, the allowed value range is *min* .. *max*-1.

Let's look at some examples. An unconstrained :class:`intbv` object is created
as follows::

  >>> a = intbv(24)

.. index::
    single: intbv; min
    single: intbv; max
    single: intbv; bit width

After object creation, *min* and *max* are available as attributes for
inspection. Also, the standard Python function :func:`len` can be used
to determine the bit width. If we inspect the previously created
object, we get::

  >>> a
  intbv(24)
  >>> print(a.min)
  None
  >>> print(a.max)
  None
  >>> len(a)
  0

As the instantiation was unconstrained, the *min* and *max* attributes
are undefined. Likewise, the bit width is undefined, which is indicated
by a return value ``0``.

A constrained :class:`intbv` object is created as follows:

  >>> a = intbv(24, min=0, max=25)

Inspecting the object now gives::

  >>> a
  intbv(24)
  >>> a.min
  0
  >>> a.max
  25
  >>> len(a)
  5

We see that the allowed value range is 0 .. 24,  and that 5 bits are
required to represent the object.

The *min* and *max* bound attributes enable fine-grained control and error
checking of the value range. In particular, the bound values do not have to be
symmetric or powers of 2. In all cases, the bit width is set appropriately to
represent the values in the range. For example::

  >>> a = intbv(6, min=0, max=7)
  >>> len(a)
  3
  >>> a = intbv(6, min=-3, max=7)
  >>> len(a)
  4
  >>> a = intbv(6, min=-13, max=7)
  >>> len(a)
  5

.. _hwtypes-indexing:

Bit indexing
============

.. index:: single: bit indexing

A common requirement in hardware design is access to the individual bits. The
:class:`intbv` class implements an indexing interface that provides access to
the bits of the underlying two's complement representation. The following
illustrates bit index read access::

  >>> from myhdl import bin
  >>> a = intbv(24)
  >>> bin(a)
  '11000'
  >>> int(a[0])
  0
  >>> int(a[3])
  1
  >>> b = intbv(-23)
  >>> bin(b)
  '101001'
  >>> int(b[0])
  1
  >>> int(b[3])
  1
  >>> int(b[4])
  0

We use the :func:`bin` function provide by MyHDL because it shows the two's
complement representation for negative values, unlike Python's builtin with the
same name. Note that lower indices correspond to less significant bits. The
following code illustrates bit index assignment::

  >>> bin(a)
  '11000'
  >>> a[3] = 0
  >>> bin(a)
  '10000'
  >>> a
  intbv(16)
  >>> b
  intbv(-23)
  >>> bin(b)
  '101001'
  >>> b[3] = 0
  >>> bin(b)
  '100001'
  >>> b
  intbv(-31)

.. _hwtypes-slicing:

Bit slicing
===========

.. index::
   single: bit slicing

The :class:`intbv` type also supports bit slicing, for both read access
assignment. For example::

   >>> a = intbv(24)
   >>> bin(a)
   '11000'
   >>> a[4:1]
   intbv(4)
   >>> bin(a[4:1])
   '100'
   >>> a[4:1] = 0b001
   >>> bin(a)
   '10010'
   >>> a
   intbv(18)

In accordance with the most common hardware convention, and unlike standard
Python, slicing ranges are downward.  As in standard Python, the slicing range
is half-open: the highest index bit is not included. Unlike standard Python
however, this index corresponds to the *leftmost* item.

Both indices can be omitted from the slice.  If the rightmost index is omitted,
it is ``0`` by default. If the leftmost index is omitted, the meaning is to
access "all" higher order bits. For example::

  >>> bin(a)
  '11000'
  >>> bin(a[4:])
  '1000'
  >>> a[4:] = '0001'
  >>> bin(a)
  '10001'
  >>> a[:] = 0b10101
  >>> bin(a)
  '10101'

The half-openness of a slice may seem awkward at first, but it helps to avoid
one-off count issues in practice. For example, the slice ``a[8:]`` has exactly
``8`` bits. Likewise, the slice ``a[7:2]`` has ``7-2=5`` bits. You can think
about it as follows: for a slice ``[i:j]``, only bits below index ``i`` are
included, and the bit with index ``j`` is the last bit included.

When an :class:`intbv` object is sliced, a new :class:`intbv` object is returned.
This new :class:`intbv` object is always positive, and the value bounds are
set up in accordance with the bit width specified by the slice. For example::

    >>> a = intbv(6, min=-3, max=7)
    >>> len(a)
    4
    >>> b = a[4:]
    >>> b
    intbv(6L)
    >>> len(b)
    4
    >>> b.min
    0
    >>> b.max
    16

In the example, the original object is sliced with a slice equal to its bit width.
The returned object has the same value and bit width, but its value
range consists of all positive values that can be represented by
the bit width.

The object returned by a slice is positive, even when the original object is
negative::

    >>> a = intbv(-3)
    >>> bin(a, width=5)
    '11101'
    >>> b = a[5:]
    >>> b
    intbv(29L)
    >>> bin(b)
    '11101'

In this example, the bit pattern of the two objects is identical within the bit
width, but their values have opposite sign.

Sometimes hardware engineers prefer to constrain an object by defining its bit
width directly, instead of the range of allowed values. Using the slicing
properties of the :class:`intbv` class one can do that as follows::

  >>> a = intbv(24)[5:]

What actually happens here is that first an unconstrained :class:`intbv`
is created, which is then sliced. Slicing an :class:`intbv` returns a new
:class:`intbv` with the constraints set up appropriately.
Inspecting the object now shows::

  >>> a.min
  0
  >>> a.max
  32
  >>> len(a)
  5

Note that the *max* attribute is 32, as with 5 bits it is possible to represent
the range 0 .. 31.  Creating an :class:`intbv` in this way is convenient but has
the disadvantage that only positive value ranges between 0 and a power of 2 can
be specified.

.. _hwtypes-modbv:

The :class:`modbv` class
========================

In hardware modeling, there is often a need for the elegant modeling of
wrap-around behavior. :class:`intbv` instances do not support this
automatically, as they assert that any assigned value is within the bound
constraints. However, wrap-around modeling can be straightforward.  For
example, the wrap-around condition for a counter is often decoded explicitly,
as it is needed for other purposes. Also, the modulo operator provides an
elegant one-liner in many scenarios::

    count.next = (count + 1) % 2**8

However, some interesting cases are not supported by the :class:`intbv` type.
For example, we would like to describe a free running counter using a variable
and augmented assignment as follows::

    count_var += 1

This is not possible with the :class:`intbv` type, as we cannot add the modulo
behavior to this description. A similar problem exist for an augmented left
shift as follows::

    shifter <<= 4

To support these operations directly, MyHDL provides the :class:`modbv`
type. :class:`modbv` is implemented as a subclass of  :class:`intbv`.
The two classes have an identical interface and work together
in a straightforward way for arithmetic operations.
The only difference is how the bounds are handled: out-of-bound values
result in an error with :class:`intbv`, and in wrap-around with
:class:`modbv`. For example, the modulo counter above can be
modeled as follows::

    count = Signal(modbv(0, min=0, max=2**8))
    ...
    count.next = count + 1

The wrap-around behavior is defined in general as follows::

    val = (val - min) % (max - min) + min

In a typical case when ``min==0``, this reduces to::

    val = val % max

.. _hwtypes-signed:

Unsigned and signed representation
==================================

.. index::
    single: intbv; intbv.signed

:class:`intbv` is designed to be as high level as possible. The underlying
value of an :class:`intbv` object is a Python :class:`int`, which is
represented as a two's complement number with "indefinite" bit
width. The range bounds are only used for error checking, and to
calculate the minimum required bit width for representation. As a
result, arithmetic can be performed like with normal integers.

In contrast, HDLs such as Verilog and VHDL typically require designers
to deal with representational issues, especially for synthesizable code.
They provide low-level types like ``signed`` and ``unsigned`` for
arithmetic. The rules for arithmetic with such types are much more
complicated than with plain integers.

In some cases it can be useful to interpret :class:`intbv` objects
in terms of "signed" and "unsigned". Basically, it depends on attribute *min*.
if *min* < 0, then the object is "signed", otherwise it is "unsigned".
In particular, the bit width of a "signed" object will account for
a sign bit, but that of an "unsigned" will not, because that would
be redundant. From earlier sections, we have learned that the
return value from a slicing operation is always "unsigned".

In some applications, it is desirable to convert an "unsigned"
:class:`intbv` to  a "signed", in other words, to interpret the msb bit
as a sign bit.  The msb bit is the highest order bit within the object's
bit width.  For this purpose, :class:`intbv` provides the
:meth:`intbv.signed` method. For example::

    >>> a = intbv(12, min=0, max=16)
    >>> bin(a)
    '1100'
    >>> b = a.signed()
    >>> b
    -4
    >>> bin(b, width=4)
    '1100'

:meth:`intbv.signed` extends the msb bit into the higher-order bits of the
underlying object value, and returns the result as an integer.
Naturally, for a "signed" the return value will always be identical
to the original value, as it has the sign bit already.

As an example let's take a 8 bit wide data bus that would be modeled as
follows::

  data_bus = intbv(0)[8:]

Now consider that a complex number is transferred over this data
bus. The upper 4 bits of the data bus are used for the real value and
the lower 4 bits for the imaginary value. As real and imaginary values
have a positive and negative value range, we can slice them off from
the data bus and convert them as follows::

 real.next = data_bus[8:4].signed()
 imag.next = data_bus[4:].signed()

 
 .. _hwtypes-fixbv:

The :class:`fixbv` class
========================

.. index:: single: fixbv; basic usage


Introduction (Motivation)
-------------------------

    Constrained [1]_ integer numbers, such as :class:`intbv`, are the foundation
    for hardware development.  But in some cases real numbers,
    numbers with fraction, are more appropriate.  This is certainly
    true with digital signal processing applications.  This document
    proposes a fixed-point bit-vector type, :class:`fixbv`, to represent
    signed rational real numbers.

    The fixed-point type provides a mechanism to represent a constrained
    real number with the same hardware realization required by the
    integers - which is not the case for floating-point types.


Specification
-------------
   A review of the fixed-point representation is required before
   presenting the :class:`fixbv` specification.

What is fixed-point
^^^^^^^^^^^^^^^^^^^
   Most people are familiar with fixed-point and floating-point
   representation but by slightly different names and a different
   base.  When dealing with real numbers we commonly write real
   numbers either in fixed-point or scientific notation
   (floating-point)

   decimal fixed-point (everyday usage): ::

      845.7073

   scientific notation (floating-point): ::

      1.12e9

   The binary version are similar, with binary fixed-point the
   bits to the left of the "point" is the *integer part*, the
   positive powers of two, and to the right of the point are negative 
   powers of two, the *fraction*:

   The *point* is a logical assignment, there is nothing that
   locks the point to a position.  The point logically defines
   the number of integer bits and fractional bits and is required
   when interpreting the number and performing operations.

   Binary fixed-point does not restrict the number of bits
   (width) to be positive values, negative number of bits is
   possible to represent the integer or fractional widths.  
   It is possible to have a negative number of integer or
   fractional bits.  Example, if the number of integer bits
   is -4 there are no integer bits and the fractional
   has four place holders.

   As mentioned, binary fixed-point representation is similar to
   every day usages of real numbers, that is a "decimal point" is
   used to separate the integer portion of the real number from
   the fractional portion, example: ::

       s : sign bit
       i : integer bits
       f : fractional bits

       siii.ffff
       0011.1000

   The above example is an 8-bit bit-vector with three
   integer bits and four fractional bits.  As described,
   the fractional value is a combination of negative powers
   of two, analogous, the integer value is a combination of
   positive powers of two.  The value represented by the
   above example is 3.5.

   The following computes the first eight negative powers
   of two:

    >>> [2 ** (-1 * ii) for ii in range(1, 9)]
    [0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625, 0.0078125, 0.00390625]


Resolution
^^^^^^^^^^

   The resolution is the smallest quantity representable.  The resolution
   is defined by the number of fractional bits, $ 2^{-fwl} $.  It indicates
   what the minium increment quantity is.  

Range
^^^^^

   The range of the :class:`fixbv` is the maximum and minimum values.  The maximum
   values is actually max-res.  The max is $2^{iwl}-res$ and the min is
   $-2^{iwl}$.


The :class:`fixbv` class
------------------------

   Creating a :class:`fixbv` object should be straightforward and an extension
   to the natural usage of real numbers.  Because the :class:`fixbv` represents
   a constrained range and resolution, these need to be defined when
   creating a fixed-point type.  When creating a :class:`fixbv` the initial value,
   minimum, maximum, and number of fractional bits are defined, example: ::

       x = fixbv(0.333, fmin=-1.0, fmax=1.0, fractionalbits=8)    


   Although MEP 111 proposed ::
   
       x = fixbv(0.333, fmin=-1.0, fmax=1.0, res=0.1) 
   
   In many cases the requested resolution (*res*) cannot be encoded 
   exactly with a reasonable number of bits. 
   The resolution would be rounded down to the closest power of two.
   
   In the above :class:`fixbv` creation the requested resolution is 0.1
   but the generated resolution will be 0.0625.  This resolution is
   better than the 0.1 but will have the downside that multiples of
   the requested resolution cannot be represented exactly.  

   If the goal is to encode 0.1, 0.2, 0.3, 0.4, etc., it cannot be
   accomplished with a finite number of bits.  The basic idea: if
   one of the denominator's prime multiples (e.g. 2 and 5 for
   10) is not a multiple of the base then the rational fraction
   cannot be represented exactly.  Stated differently, each of
   the denominator's prime factors needs to be a multiple of the
   base to be represented exactly.

   If the initial value cannot be represented exactly or the initial
   value defines a greater precision than the :class:`fixbv` can encode
   the value will be rounded, using the  convergent rounding as used in IEEE754.


   Using `res=` will be confusing so we opted for a direct specification
   of the number of fractional bits required. As this calculation will 
   eventually performed anyway ...
   
   .. index:: single: fixbv; operations

   First, lets review fixed-point mathematics, given two fixed-point
   variables, *x* and *y*: ::

	   x = fixbv(0, min=-8, max=8, fractionalbits=4) # siii.ffff
	   y = fixbv(0, min=-1, max=1, fractionalbits=7) # s.fffffff

   Addition and subtraction require the operands to be aligned,
   they don't necessarily need to be the same word-length (wl) but
   the "point" needs to be aligned, using the above as operands: ::

         siii.ffff000
       + ssss.fffffff
       --------------
        siiii.fffffff

   once the operands are aligned normal 2's complement addition/
   subtraction can be performed.  The maximum result would be
   2\*max(x.max,y.max) (or max(len(x),len(y))+1). 
   Both addition and subtraction will align the decimal points and the returned
   result will have the greater of the two fractionalbits
   
   :class:`fixbv` operations will return an :class:`_FixbvResult`.::

       >>> x1 = fixbv(2.50, fmin=-8, fmax=8, fractionalbits=4)
       >>> x2 = fixbv(1.25, fmin=-8, fmax=8, fractionalbits=4)
       >>> a = x1 + x2
       >>> a
      _FixbvResult(real=3.75, vector=60, fractionalbits=4)


   :class:`_FixbvResult` was introduced as it has a much smaller footprint than 
   :class:`fixbv` itself.
   Note that the user doesn't have care about :class:`_FixbvResult` as the MyHDL 
   package handles this internally.
   When assigned to another :class:`fixbv` the :class:`_FixbvResult` value will fit
   in the format of the accepting object.::

       >>> x1 = fixbv(2.50, fmin=-8, fmax=8, fractionalbits=4)
       >>> x2 = fixbv(1.25, fmin=-8, fmax=8, fractionalbits=4)
	   >>> z = fixbv(0, fmin=-16, fmax=16,  fractionalbits=4)
	   >>> z[:] = x1 + x2
	   >>> z
	   fixbv(3.75, fmin=-16, fmax=16, fractionalbits=4)

   For multiplication the operands do not need to be aligned before
   the operation but the "point" bookkeeping needs to be accounted.::

               siii.ffff
       *       s.fffffff
       -----------------
       ssiii.fffffffffff  (total 16 bits)

   A multiplication example: ::

	   >>> x = fixbv( 1.5, fmin=-8.0, fmax=8.0, fractionalbits=8)
	   >>> y = fixbv(-2.0, fmin=-8.0, fmax=8.0, fractionalbits=8)
	   >>> z = x * y
	   >>> z
	   _FixbvResult(real=-5.0, vector=-327680 with fractionalbits=16)
	   >>> myhdl.bin(z.vector)
	   '10110000000000000000'


   The basic mathematical operations have been reviewed, we will
   exclude division for now because we can achieve "division"
   by multiplying by the fractional parts.

   The next topic: rounding and overflow handling.  During operations
   it is common not to maintain the maximum word-length through out a
   chain of operations.  When reducing the word-length rounding and
   overflow come into play.  

   Example, multiplying two numbers requires len(x) + len(y) bits or
   x.max \* y.max range.  It is typical for the result to be *resized*
   after an operation.  In the previous multiply example it may be
   desired to only preserve four fraction bits: ::

       ssiii.fffffffffff
                  ~~~~~~ <- these bits remove

   The remaining bits will be rounded based on the removed bits,
   there are different rounding methods that can be used.  This is
   a base feature of a fixed-point package.  Also, when resizing
   overflow (underflow) is also an issue.  If the value being
   resized does not fit, it needs to be saturated or wrapped.

   A *resize* function is not implemented.
   As a *work-around* the user can define a function to achieve the same.
   Note that removing bits is easily achieved by slicing:
   
       >>> g = fixbv(-3.14159, fmin=-4.0, fmax=4.0, fractionalbits=16)
       >>> g.ord
       -205887
       >>> g.bin
       '100.1101101111000001'
       >>>gs = g[:4]
       >> gs
       _FixbvResult(real=-3.14159, vector=-12868, fractionalbits=0)
   
   The *real* value will be preserved!

Simulation
^^^^^^^^^^

   A gem of :class:`fixbv` is that during :class:`Simulation` it tracks 
   both the `integer` bit representation **and** the `real` floating point
   representation.
   The :class:`trace`, if enabled, writes both *values* to the `.vcd` ouput file;
   the *integer* is marked by `<signame>_vector` and the *real* is marked by
   `<signame>_real` as shown in the following image:

    .. image:: Simulation_fixbv_cosim.png
	

Conversion
^^^^^^^^^^

   The beauty of the :class:`fixbv` is that it is a subclass of 
   :class:`intbv`.  This makes sense because the fixed-point is an
   integer representation at the hardware.  Nothing is required
   for conversion, the fixed-point is simply a logical representation
   of a limited capacity (constrained) real number implemented with
   a standard 2's complement integer.

   A couple :class:`fixbv` *properties* are included to support
   convertible conversion to other type: ::

      # fixbv.integer : this will return just the integer
      # fixbv.ord : the underlying intbv value
      # fixbv.fractional : just the fraction portion


      >>> x = fixbv(2.5, fmin=-8.0, fmax=8.0, fractionalbits=8)
      >>> x.integer
      2
      >>> x.ord
      640
      >>> x.fractional
      128

   These properties are necessary because the factory functions
   int() and ord() are not convertible, this is consistent with
   the current implementation (other than the current
   implementation would have no need to use int(intbv()).


Limitations
^^^^^^^^^^^

   - `int(fixbv)` and `float(fixbv)` are not convertible.  They can
     be used in the elaboration and other non-convertible code.

   - no *resize* function (yet).  As discussed the *resize*
     function is dependent (as best understanding) on an
     additional `enhancement`.  The resize function will be
     added once the `modfunc` enhancement has been implemented.
     It is my opinion fixed-point support needs the resize function
     but it will be part of a separate enhancement proposal

   - no division (no surprise, same operation limitations as
     integer, divide by power of two's)


Closing Remarks
^^^^^^^^^^^^^^^

   The :class:`fixbv` type provides a clean an straightforward type to
   represent constrained real numbers (fixed-point numbers).  The
   :class:`fixbv` provides the basic number representation.  The addition
   of the *resize* will complete the fixed-point support.


.. rubric:: Footnotes

.. [1] here we are using `constrained integer` and `constrained real` to
       indicate numbers with limited range and resolution.  The
       type will act just like an integer or real within the
       constrained (the range and resolution).
