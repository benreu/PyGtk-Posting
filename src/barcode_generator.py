# barcode_generator.py
# Copyright (C) 2018 reuben
# 
# barcode_generator.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# barcode_generator.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

CharSetA =  {
' ':0, '!':1, '"':2, '#':3, '$':4, '%':5, '&':6, "'":7,
'(':8, ')':9, '*':10, '+':11, ',':12, '-':13, '.':14, '/':15,
'0':16, '1':17, '2':18, '3':19, '4':20, '5':21, '6':22, '7':23,
'8':24, '9':25, ':':26, ';':27, '<':28, '=':29, '>':30, '?':31,
'@':32, 'A':33, 'B':34, 'C':35, 'D':36, 'E':37, 'F':38, 'G':39,
'H':40, 'I':41, 'J':42, 'K':43, 'L':44, 'M':45, 'N':46, 'O':47,
'P':48, 'Q':49, 'R':50, 'S':51, 'T':52, 'U':53, 'V':54, 'W':55,
'X':56, 'Y':57, 'Z':58, '[':59, '\\':60, ']':61, '^':62, '_':63,
'\x00':64, '\x01':65, '\x02':66, '\x03':67, '\x04':68, '\x05':69, '\x06':70, '\x07':71,
'\x08':72, '\x09':73, '\x0A':74, '\x0B':75, '\x0C':76, '\x0D':77, '\x0E':78, '\x0F':79,
'\x10':80, '\x11':81, '\x12':82, '\x13':83, '\x14':84, '\x15':85, '\x16':86, '\x17':87,
'\x18':88, '\x19':89, '\x1A':90, '\x1B':91, '\x1C':92, '\x1D':93, '\x1E':94, '\x1F':95,
'FNC3':96, 'FNC2':97, 'SHIFT':98, 'Code C':99, 'Code B':100, 'FNC4':101, 'FNC1':102, 'START A':103,
'START B':104, 'START C':105, 'STOP':106
 }

CharSetB = {
' ':0, '!':1, '"':2, '#':3, '$':4, '%':5, '&':6, "'":7,
'(':8, ')':9, '*':10, '+':11, ',':12, '-':13, '.':14, '/':15,
'0':16, '1':17, '2':18, '3':19, '4':20, '5':21, '6':22, '7':23,
'8':24, '9':25, ':':26, ';':27, '<':28, '=':29, '>':30, '?':31,
'@':32, 'A':33, 'B':34, 'C':35, 'D':36, 'E':37, 'F':38, 'G':39,
'H':40, 'I':41, 'J':42, 'K':43, 'L':44, 'M':45, 'N':46, 'O':47,
'P':48, 'Q':49, 'R':50, 'S':51, 'T':52, 'U':53, 'V':54, 'W':55,
'X':56, 'Y':57, 'Z':58, '[':59, '\\':60, ']':61, '^':62, '_':63,
'' :64, 'a':65, 'b':66, 'c':67, 'd':68, 'e':69, 'f':70, 'g':71,
'h':72, 'i':73, 'j':74, 'k':75, 'l':76, 'm':77, 'n':78, 'o':79,
'p':80, 'q':81, 'r':82, 's':83, 't':84, 'u':85, 'v':86, 'w':87,
'x':88, 'y':89, 'z':90, '{':91, '|':92, '}':93, '~':94, '\x7F':95,
'FNC3':96, 'FNC2':97, 'SHIFT':98, 'Code C':99, 'FNC4':100, 'Code A':101, 'FNC1':102, 'START A':103,
'START B':104, 'START C':105, 'STOP':106
}

CharSetC = {
'00':0, '01':1, '02':2, '03':3, '04':4, '05':5, '06':6, '07':7,
'08':8, '09':9, '10':10, '11':11, '12':12, '13':13, '14':14, '15':15,
'16':16, '17':17, '18':18, '19':19, '20':20, '21':21, '22':22, '23':23,
'24':24, '25':25, '26':26, '27':27, '28':28, '29':29, '30':30, '31':31,
'32':32, '33':33, '34':34, '35':35, '36':36, '37':37, '38':38, '39':39,
'40':40, '41':41, '42':42, '43':43, '44':44, '45':45, '46':46, '47':47,
'48':48, '49':49, '50':50, '51':51, '52':52, '53':53, '54':54, '55':55,
'56':56, '57':57, '58':58, '59':59, '60':60, '61':61, '62':62, '63':63,
'64':64, '65':65, '66':66, '67':67, '68':68, '69':69, '70':70, '71':71,
'72':72, '73':73, '74':74, '75':75, '76':76, '77':77, '78':78, '79':79,
'80':80, '81':81, '82':82, '83':83, '84':84, '85':85, '86':86, '87':87,
'88':88, '89':89, '90':90, '91':91, '92':92, '93':93, '94':94, '95':95,
'96':96, '97':97, '98':98, '99':99, 'Code B':100, 'Code A':101, 'FNC1':102, 'START A':103,
'START B':104, 'START C':105, 'STOP':106
}

def makeCode128(code):

	current_charset = None
	pos=sum=0
	skip=False
	for c in range(len(code)):
		if skip:
			skip=False
			continue
		#Only switch to char set C if next four chars are digits
		if len(code[c:]) >=4 and code[c:c+4].isdigit() \
			and current_charset!=CharSetC or \
			len(code[c:]) >=2 and code[c:c+2].isdigit() \
			and current_charset==CharSetC:
			#If char set C = current and next two chars ar digits, keep C
			if current_charset!=CharSetC:
				#Switching to Character set C
				if pos:
					code_list.append (current_charset['Code C'])
					sum  += pos * current_charset['Code C']
				else:
					code_list = [CharSetC['START C']]
					sum = CharSetC['START C']
				current_charset= CharSetC
				pos+=1
		elif code[c] in CharSetB and current_charset!=CharSetB and \
			not(code[c] in CharSetA and current_charset==CharSetA):
			#If char in chrset A = current, then just keep that
			# Switching to Character set B
			if pos:
				code_list.append (current_charset['Code B'])
				sum  += pos * current_charset['Code B']
			else:
				code_list = [CharSetB['START B']]
				sum = CharSetB['START B']
			current_charset= CharSetB
			pos+=1
		elif code[c] in CharSetA and current_charset!=CharSetA and \
			not(code[c] in CharSetB and current_charset==CharSetB):
			# if char in chrset B== current, then just keep that
			# Switching to Character set A
			if pos:
				code_list.append (current_charset['Code A'])
				sum  += pos * current_charset['Code A']
			else:
				code_list.append (CharSetA['START A'])
				sum = CharSetA['START A']
			current_charset= CharSetA
			pos+=1
		if current_charset==CharSetC:
			val= CharSetC[code[c:c+2]]
			skip=True
		else:
			val=current_charset[code[c]]
		sum += pos * val
		code_list.append (val)
		pos+=1
	checksum= sum % 103
	code_list.append (checksum)
	code_list.append (current_charset['STOP'])
	chars = (b'\xd4' + bytes(range(33,126+1)) + bytes(range(200,211+1))).decode('latin-1')
	return ''.join(chars[x] for x in code_list)


