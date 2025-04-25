'''
Created on 21 apr. 2025

@author: josy

    these functions will also be available in the representative
    package/include file ditributed with MyHDL

'''
import math

from myhdl._parameter import Parameter


def widthu(v):
    '''  
        returns the required width to encode the given value starting with 0
        e.g. widthu(8) = 3, widthu(7) = 3 (also)
        *v* can be negative
    '''
    # default to 'unsigned'
    # print(f'widthu: processing {v=}')
    tv = v
    if v < 0:
        # using signed numbers requires double
        tv = -v * 2
    if tv == 0:
        raise ValueError("widthu: O-value has no width")
    elif tv == 1:
        print("widthu: 1-value is singular")
        r = 0
    else:
        r = int(math.ceil(math.log(tv, 2)))
    return Parameter(r) if isinstance(v, Parameter) else r


def widthr(v):
    ''' 
        returns the required width to represent the given number
        e.g. widthr(8) = 4
        *v* can be negative
    '''
    # default to 'unsigned'
    tv = v
    if v < 0:
        # using signed numbers requires double
        tv = -v * 2
    if tv == 0:
        raise ValueError("widthr: O-value has no width")
    elif tv == 1:
        return 1
    else:
        exp = math.ceil(math.log(tv, 2))
        if math.pow(2, exp) == tv:
            exp += 1

    r = int(exp)
    return Parameter(r) if isinstance(v, Parameter) else r


if __name__ == '__main__':
    pass
