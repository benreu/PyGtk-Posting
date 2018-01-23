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
	db_settings \
	src/PyGtk_Posting.svg \
	run.sh \
	pygtk_posting.anjuta \
	POSTGRES_README 



# Remove doc directory on uninstall
uninstall-local:
	-rm -r $(docdir)
