import unittest
from unittest import mock
from harness import DBTestCase
from gi.repository import Gtk, GLib

class ShowMessageTest(DBTestCase):
	def test_missing_serial_number_dialog_can_be_shown(self):
		from manufacturing import projects
		fake_self = mock.Mock()
		fake_self.window = Gtk.Window()
		with mock.patch.object(Gtk.MessageDialog, 'run') as run:
			projects.ManufacturingProjectsGUI.show_message(fake_self, "Missing serial numbers!")
		run.assert_called_once()

class PostShortProjectTest(DBTestCase):
	'''posting a build whose components are short at the location they come
	from. The stock is allowed to go negative, the way a sale's is, but the user
	is asked first -- before anything is written, so declining changes nothing'''
	def setUp(self):
		super().setUp()
		from manufacturing import projects
		self.module = projects
		self.cursor.execute("SELECT mp.id, mp.product_id "
							"FROM manufacturing_projects AS mp "
							"WHERE (SELECT count(*) FROM manufacturing_items "
							"WHERE manufacturing_project_id = mp.id "
							"AND qty > 0) >= 2 "
							"AND mp.qty > 0 AND mp.active LIMIT 1")
		self.project_id, self.product_id = self.cursor.fetchone()
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0 "
							"ORDER BY product_id", (self.project_id,))
		self.component_id, self.needed = self.cursor.fetchall()[0]
		# the components have to be tracked before any of this moves stock, and
		# the build has to be postable without a serial number prompt
		self.cursor.execute("UPDATE products SET inventory_enabled = True, "
							"inventory_account = 1761 WHERE id = %s OR id IN "
							"(SELECT product_id FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s)",
							(self.product_id, self.project_id))
		self.cursor.execute("UPDATE products "
							"SET invoice_serial_numbers = False "
							"WHERE id = %s", (self.product_id,))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE manufacturing_id = %s", (self.project_id,))
		self.source_id = self.new_location('Test source')
		self.cursor.execute("UPDATE manufacturing_items "
							"SET source_location_id = %s "
							"WHERE manufacturing_project_id = %s",
							(self.source_id, self.project_id))
		self.DB.commit() # the window rolls back after every read of its own

	def open_projects(self):
		gui = self.module.ManufacturingProjectsGUI()
		selection = gui.get_object('treeview-selection')
		for row in gui.get_object('manufacturing_store'):
			if row[0] == self.project_id:
				selection.select_iter(row.iter)
				return gui
		self.fail('the project under test is not in the list')

	def every_line(self):
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0",
							(self.project_id,))
		return self.cursor.fetchall()

	def post(self, response):
		gui = self.open_projects()
		with mock.patch.object(Gtk.MessageDialog, 'set_markup') as set_markup, \
				mock.patch.object(Gtk.MessageDialog, 'run',
									return_value = response) as run:
			gui.post_project_clicked(None)
		run.assert_called_once()
		return set_markup.call_args[0][0]

	def test_the_warning_names_the_part_and_the_location_it_is_short_at(self):
		name = self.one("SELECT name FROM products WHERE id = %s",
						(self.component_id,))
		shown = self.post(Gtk.ResponseType.NO)
		self.assertIn(GLib.markup_escape_text(name), shown)
		self.assertIn('Test source', shown)

	def test_declining_leaves_the_project_untouched(self):
		self.post(Gtk.ResponseType.NO)
		self.assertTrue(self.one("SELECT active FROM manufacturing_projects "
								"WHERE id = %s", (self.project_id,)))
		self.assertEqual(self.one("SELECT count(*) "
								"FROM inventory_transactions "
								"WHERE manufacturing_id = %s",
								(self.project_id,)), 0)

	def test_accepting_posts_the_build_and_takes_the_stock_negative(self):
		'''the count may be off and the build has already happened, so the post
		is allowed to go through -- it is only never silent'''
		self.post(Gtk.ResponseType.YES)
		self.assertFalse(self.one("SELECT active FROM manufacturing_projects "
								"WHERE id = %s", (self.project_id,)))
		self.assertEqual(self.on_hand(self.component_id, self.source_id),
						-self.needed)

	def test_a_covered_build_posts_without_asking(self):
		for product_id, qty in self.every_line():
			self.cursor.execute("INSERT INTO inventory_transactions "
								"(product_id, qty_in, price, location_id, "
								"date_inserted, reason) "
								"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
								(product_id, qty, self.source_id))
		self.DB.commit()
		gui = self.open_projects()
		with mock.patch.object(Gtk.MessageDialog, 'run') as run:
			gui.post_project_clicked(None)
		run.assert_not_called()
		self.assertFalse(self.one("SELECT active FROM manufacturing_projects "
								"WHERE id = %s", (self.project_id,)))


if __name__ == '__main__':
	unittest.main()
