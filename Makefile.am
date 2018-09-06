## Process this file with automake to produce Makefile.in
## Created by Anjuta

SUBDIRS = src \
	templates \
	help \
	logs 

dist_doc_DATA = \
	README \
	COPYING \
	ChangeLog \
	src/PyGtk_Posting.svg \
	run.sh \
	pygtk_posting.anjuta \
	POSTGRES_README \
	requirements.txt \
	setup.py 



# Remove doc directory on uninstall
uninstall-local:
	-rm -r $(docdir)
