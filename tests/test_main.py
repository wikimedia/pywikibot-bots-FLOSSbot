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
import logging

import FLOSSbot.qa
import mock
from FLOSSbot import main


class TestFLOSSbot(object):

    @mock.patch.object(FLOSSbot.qa.QA, 'run')
    def test_run(self, m_run):
        f = main.FLOSSbot()

        argv = ['qa']
        f.run(['--verbose'] + argv)
        assert (logging.getLogger('FLOSSbot').getEffectiveLevel() ==
                logging.DEBUG)

        f.run(argv)
        assert (logging.getLogger('FLOSSbot').getEffectiveLevel() ==
                logging.INFO)

# Local Variables:
# compile-command: "cd .. ; tox -e py3 tests/test_main.py"
# End:
