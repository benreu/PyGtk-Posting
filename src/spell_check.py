# spell_check.py
#
# Copyright (C) 2017 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

def add_checker_to_widget (textview):
	"adds a spell checker to a textview"
	try:
		import gi
		gi.require_version('GtkSpell', '3.0')
		from gi.repository import GtkSpell
	except ValueError as e:
		print (e), "please install gir1.2-gtkspell"
		return
	spell = GtkSpell.Checker()
	spell.set_language("en_US")
	spell.attach(textview)
