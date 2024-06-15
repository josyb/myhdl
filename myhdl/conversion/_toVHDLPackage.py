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

import myhdl

vMajor, vminor, vsubminor = myhdl.__version__.split('.')

_package = f"""\
library ieee;
    use ieee.std_logic_1164.all;
    use ieee.numeric_std.all;

package pck_myhdl is

    type version is record 
        Major : integer;
        minor : integer;
        subminor : integer;
    end record version;
    Constant PackageVersion : version := (Major => {vMajor}, minor => {vminor}, subminor => {vsubminor});
        
    function check_package_version(Major: integer; minor: integer; subminor: integer) return boolean;
    
    type array_of_sl is array (natural range <>) of std_logic;
    type array_of_slv is array (natural range <>) of std_logic_vector;
    type array_of_unsigned is array (natural range <>) of unsigned;
    type array_of_signed is array (natural range <>) of signed;

    attribute enum_encoding: string;

    function to_std_logic_vector(aslv : array_of_slv) return std_logic_vector;
    function to_unsigned(au : array_of_unsigned) return unsigned;
    function to_unsigned(as : array_of_signed) return unsigned;
    function to_array(slv : std_logic_vector; width : natural) return array_of_slv;
    function to_array(vu : unsigned; width : natural) return array_of_unsigned;
    function to_array(vs : unsigned; width : natural) return array_of_signed;

    function stdl (arg: boolean) return std_logic;
    function stdl (arg: integer) return std_logic;

    function to_unsigned (arg: boolean; size: natural) return unsigned;
    function to_unsigned (arg: std_logic; size: natural) return unsigned;

    function to_signed (arg: boolean; size: natural) return signed;
    function to_signed (arg: std_logic; size: natural) return signed;

    function to_integer(arg: boolean) return integer;
    function to_integer(arg: std_logic) return integer;



    function bool (arg: std_logic) return boolean;
    function bool (arg: unsigned) return boolean;
    function bool (arg: signed) return boolean;
    function bool (arg: integer) return boolean;

    function "-" (arg: unsigned) return signed;

    function tern_op(cond: boolean; if_true: std_logic; if_false: std_logic) return std_logic;
    function tern_op(cond: boolean; if_true: unsigned; if_false: unsigned) return unsigned;
    function tern_op(cond: boolean; if_true: signed; if_false: signed) return signed;
    function tern_op(cond: boolean; if_true: integer; if_false: integer) return integer;

end pck_myhdl;


package body pck_myhdl is

    function check_package_version(Major: integer; minor: integer; subminor: integer) return boolean is
        variable r : boolean := False;
    begin
        if PackageVersion.Major > Major then
            r := True;
        elsif PackageVersion.Major = Major then
            if PackageVersion.minor > minor then 
                r := True;
            elsif PackageVersion.minor = minor then
                if PackageVersion.subminor >= subminor then
                    r := True;
                end if;
            end if;
        end if;
        return r;
    end function;

    function to_std_logic_vector(aslv : array_of_slv) return std_logic_vector is
        constant w : natural := 1 + aslv(0)'high - aslv(0)'low;
        variable r : std_logic_vector(aslv'length * w - 1 downto 0);
    begin
        for i in 0 to aslv'high loop
            r((i + 1) * w - 1 downto i * w) := aslv(i);
        end loop;
        return r;
    end function;

    function to_unsigned(au : array_of_unsigned) return unsigned is
        constant w : natural := 1 + au(0)'high - au(0)'low;
        variable r : unsigned(au'length * w - 1 downto 0);
    begin
        for i in 0 to au'high loop
            r((i + 1) * w - 1 downto i * w) := au(i);
        end loop;
        return r;
    end function;

    function to_unsigned(as : array_of_signed) return unsigned is
        constant w : natural := 1 + as(0)'high - as(0)'low;
        variable r : unsigned(as'length * w - 1 downto 0);
    begin
        for i in 0 to as'high loop
            r((i + 1) * w - 1 downto i * w) := unsigned(as(i));
        end loop;
        return r;
    end function;

    function to_array(slv : std_logic_vector; width : natural) return array_of_slv is
        constant NUM_ELEMENTS : natural := (slv'high - slv'low + 1) / width;
        variable r            : array_of_slv(0 to NUM_ELEMENTS - 1)(width - 1 downto 0);
    begin
        for i in 0 to NUM_ELEMENTS - 1 loop
            r(i) := slv((i + 1) * width - 1 downto i * width);
        end loop;
        return r;
    end function;

    function to_array(vu : unsigned; width : natural) return array_of_unsigned is
        constant NUM_ELEMENTS : natural := (vu'high - vu'low + 1) / width;
        variable r            : array_of_unsigned(0 to NUM_ELEMENTS - 1)(width - 1 downto 0);
    begin
        for i in 0 to NUM_ELEMENTS - 1 loop
            r(i) := vu((i + 1) * width - 1 downto i * width);
        end loop;
        return r;
    end function;
    
    function to_array(vs : unsigned; width : natural) return array_of_signed is
        constant NUM_ELEMENTS : natural := (vs'high - vs'low + 1) / width;
        variable r            : array_of_signed(0 to NUM_ELEMENTS - 1)(width - 1 downto 0);
    begin
        for i in 0 to NUM_ELEMENTS - 1 loop
            r(i) := signed(vs((i + 1) * width - 1 downto i * width));
        end loop;
        return r;
    end function;
        
    function stdl (arg: boolean) return std_logic is
    begin
        if arg then
            return '1';
        else
            return '0';
        end if;
    end function stdl;

    function stdl (arg: integer) return std_logic is
    begin
        if arg /= 0 then
            return '1';
        else
            return '0';
        end if;
    end function stdl;


    function to_unsigned (arg: boolean; size: natural) return unsigned is
        variable res: unsigned(size-1 downto 0) := (others => '0');
    begin
        if arg then
            res(0):= '1';
        end if;
        return res;
    end function to_unsigned;

    function to_signed (arg: boolean; size: natural) return signed is
        variable res: signed(size-1 downto 0) := (others => '0');
    begin
        if arg then
            res(0) := '1';
        end if;
        return res; 
    end function to_signed;

    function to_integer(arg: boolean) return integer is
    begin
        if arg then
            return 1;
        else
            return 0;
        end if;
    end function to_integer;

    function to_integer(arg: std_logic) return integer is
    begin
        if arg = '1' then
            return 1;
        else
            return 0;
        end if;
    end function to_integer;

    function to_unsigned (arg: std_logic; size: natural) return unsigned is
        variable res: unsigned(size-1 downto 0) := (others => '0');
    begin
        res(0):= arg;
        return res;
    end function to_unsigned;

    function to_signed (arg: std_logic; size: natural) return signed is
        variable res: signed(size-1 downto 0) := (others => '0');
    begin
        res(0) := arg;
        return res; 
    end function to_signed;

    function bool (arg: std_logic) return boolean is
    begin
        return arg = '1';
    end function bool;

    function bool (arg: unsigned) return boolean is
    begin
        return arg /= 0;
    end function bool;

    function bool (arg: signed) return boolean is
    begin
        return arg /= 0;
    end function bool;

    function bool (arg: integer) return boolean is
    begin
        return arg /= 0;
    end function bool;

    function "-" (arg: unsigned) return signed is
    begin
        return - signed(resize(arg, arg'length+1));
    end function "-";

    function tern_op(cond: boolean; if_true: std_logic; if_false: std_logic) return std_logic is
    begin
        if cond then
            return if_true;
        else
            return if_false;
        end if;
    end function tern_op;

    function tern_op(cond: boolean; if_true: unsigned; if_false: unsigned) return unsigned is
    begin
        if cond then
            return if_true;
        else
            return if_false;
        end if;
    end function tern_op;

    function tern_op(cond: boolean; if_true: signed; if_false: signed) return signed is
    begin
        if cond then
            return if_true;
        else
            return if_false;
        end if;
    end function tern_op;

    function tern_op(cond: boolean; if_true: integer; if_false: integer) return integer is
    begin
        if cond then
            return if_true;
        else
            return if_false;
        end if;
    end function tern_op;


end pck_myhdl;

"""
