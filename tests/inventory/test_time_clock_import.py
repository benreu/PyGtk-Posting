import unittest
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase

class TimeClockImportRoundingTest(DBTestCase):
	'''The time clock import bills the checked entries rounded up to the next
	tenth of an hour. The tenths were counted from the minutes past the hour
	and never carried, so anything over 54 minutes came to ten tenths:
	55 minutes was billed as "0.10" hours instead of "1.0"'''
	def setUp(self):
		super().setUp()
		from invoice import import_time_clock_entries
		customer_id = self.one("SELECT id FROM contacts "
								"WHERE (deleted, customer) = (False, True) "
								"ORDER BY id LIMIT 1")
		self.gui = import_time_clock_entries.ImportGUI(None, str(customer_id),
														None, None)
		self.addCleanup(self.gui.window.destroy)
		self.gui.import_store.clear()

	def total(self, *entries):
		'''(seconds, checked) for each entry; returns the hours to bill'''
		for row_id, (seconds, checked) in enumerate(entries):
			self.gui.import_store.append([row_id, 'Test job', seconds, '', '',
											'', checked])
		self.gui.calculate_total_time()
		label = self.gui.builder.get_object('label4').get_label()
		self.assertEqual(label, self.gui.invoicing_time)
		return self.gui.invoicing_time

	def test_55_minutes_is_a_whole_hour(self):
		self.assertEqual(self.total((55 * 60, True)), '1.0')
		self.assertEqual(self.gui.builder.get_object('label2').get_label(),
						'0:55:00')

	def test_a_second_over_54_minutes_is_a_whole_hour(self):
		self.assertEqual(self.total((54 * 60 + 1, True)), '1.0')

	def test_the_carry_goes_into_the_hours(self):
		self.assertEqual(self.total((119 * 60, True)), '2.0')

	def test_exact_tenths_are_not_rounded_up(self):
		self.assertEqual(self.total((54 * 60, True)), '0.9')
		self.gui.import_store.clear()
		self.assertEqual(self.total((6 * 60, True)), '0.1')

	def test_part_of_a_tenth_rounds_up(self):
		self.assertEqual(self.total((6 * 60 + 1, True)), '0.2')

	def test_nothing_checked_is_nothing(self):
		self.assertEqual(self.total((55 * 60, False)), '0.0')

	def test_only_checked_entries_are_added_up(self):
		self.assertEqual(self.total((30 * 60, True), (25 * 60, True),
									(40 * 60, False)), '1.0')

if __name__ == '__main__':
	unittest.main()
