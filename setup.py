import os
from setuptools import setup, find_packages

install_requires = open("requirements.txt").read().split('\n')
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "PyGtkPosting",
    version = "0.4.1",
    author = "Reuben Rissler",
    author_email = "pygtk.posting@gmail.com",
    description = ("An accounting program for Linux."),
    long_description=read('README'),
    license = ["GPLv3", "LGPLv3"],
    keywords = "accounting",
    url = "https://github.com/benreu/PyGtk-Posting",
    install_requires=install_requires,
    packages=['templates', 
                'src', 
                'src.admin', 
                'src.invoice',
                'src.db',
                'src.inventory',
                'src.pdf_opt',
                'src.pdf_opt.pdfsizeopt_libexec',
                'src.reports',
                'src.payroll'],
    package_data = {
        'src.pdf_opt': ['*'],
        'src.pdf_opt.pdfsizeopt_libexec': ['*'],
        '': ['*.ui'],
        'templates': ['*.odt'],
        'help': ['*.page']
    }
)


