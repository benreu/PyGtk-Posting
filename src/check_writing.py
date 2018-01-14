# check_writing.py
#
# Copyright (C) 2016 - reuben
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

import re

Money = (["", "one ", "two ", "three ", "four ", "five ", "six ", "seven ", "eight ", "nine ", "ten ", "eleven ", "twelve ", "thirteen ", "fourteen ", "fifteen ", "sixteen ", "seventeen ", "eighteen ", "nineteen "])

MoneyTy = (["", "onety ", "twenty ", "thirty ", "fourty ", "fifty ", "sixty ", "seventy ", "eighty ", "ninety "])

def get_check_number (db, bank_account):
	cursor = db.cursor()
	cursor.execute("SELECT MAX(check_number) FROM gl_entries "
					"WHERE credit_account = %s", (bank_account,))
	check_number = cursor.fetchone()[0]
	if check_number == None:
		check_number = 0
	check_number += 1
	return check_number

def set_written_ck_amnt_text ( text):
	amount = re.sub("[^0-9.]", "", str(text))
	dollars = "0"
	cents = "00"
	for i in amount: #take the characters one by one
		if i == ".": #look for a dot; then split it into cents and dollars
			money_split = amount.split(".")
			cents = money_split[1][0:2]
			while len(cents) < 2:
				cents= cents + "0"
			dollars = str(money_split[0])
			break
		else:
			dollars = amount
	total_money = dollars + "." + cents
	if int(dollars) > 5:
				dollars = dollars[0:5]
	if len(dollars) == 1:
		ones = dollars[len(dollars)-1]
		ones = int(ones)
		ones = Money[ones]
		money_text = ones 
		
	if len(dollars) > 1:
		tens = dollars[len(dollars)-2]
		ones = dollars[len(dollars)-1]
		if tens < "2" and tens > "0":				
			tens = tens + ones				
			tens = int(tens)
			tens = Money[tens]
			ones = ""
		else:
			tens = int(tens)
			tens = MoneyTy[tens]
			ones = int(ones)
			ones = Money[ones]
		money_text = tens + ones 
			
	if len(dollars) > 2:
		hundreds = dollars[len(dollars)-3]
		hundreds = int(hundreds)
		hundreds = Money[hundreds]
		money_text = hundreds + "hundred " + tens + ones 
		
		
	if len(dollars) > 3:
		thousands = dollars[len(dollars)-4]
		thousands = int(thousands)
		thousands = Money[thousands]
		if dollars[len(dollars)-3] != "0":
			money_text = thousands + "thousand, " + hundreds + "hundred " + tens + ones 
		else:
			money_text = thousands + "thousand, " + tens + " " + ones
		
		
	if len(dollars) > 4:
		ten_thousands = dollars[len(dollars)-5]
		thousands = dollars[len(dollars)-4]
		if ten_thousands < "2" and ten_thousands > "0":
			ten_thousands = ten_thousands + thousands
			ten_thousands = int(ten_thousands)
			ten_thousands = Money[ten_thousands]
			thousands = ""
			if dollars[len(dollars)-3] != "0":
				money_text = ten_thousands + "thousand, " + hundreds + "hundred " + tens + ones 
			else:
				money_text = ten_thousands + "thousand, " + tens + ones
		else:
			ten_thousands = int(ten_thousands)
			ten_thousands = MoneyTy[ten_thousands]
			thousands = int(thousands)
			thousands = Money[thousands]
			if dollars[len(dollars)-3] != "0":
				money_text = ten_thousands + thousands + "thousand, " + hundreds + "hundred " + tens + ones 
			else:
				money_text = ten_thousands + thousands + "thousand, " + tens + ones

	money_text_split = money_text.split(" ")
	money_text_first = money_text_split.pop(0)
	first_word = money_text_first.capitalize()
	money_text_split.insert(0,first_word)
	money_text = ' '.join(money_text_split)
	return money_text + "dollars and " + cents + " cents"



	
