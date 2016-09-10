# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 Loic Dachary <loic@dachary.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from FLOSSbot import util


class TestUtil(object):

    def test_sh_bool__returns_true_on_exit_code_zero(self):
        assert (True is util.sh_bool('true'))

    def test_sh_bool__returns_false_on_non_zero_exit_code(self):
        assert (False is util.sh_bool('false'))

    def test_sh__returns_empty_string(self):
        assert ('' == util.sh('true'))

    def test_sh__handles_utf8(self):
        assert ('€' == util.sh('echo -n €'))

    def test_sh__accepts_input(self):
        assert('Got it' == util.sh('cat', b'Got it'))
