import unittest
from unittest import mock
from harness import DBTestCase
from gi.repository import Gtk

class ShowMessageTest(DBTestCase):
	def test_missing_serial_number_dialog_can_be_shown(self):
		from manufacturing import projects
		fake_self = mock.Mock()
		fake_self.window = Gtk.Window()
		with mock.patch.object(Gtk.MessageDialog, 'run') as run:
			projects.ManufacturingProjectsGUI.show_message(fake_self, "Missing serial numbers!")
		run.assert_called_once()

if __name__ == '__main__':
	unittest.main()
