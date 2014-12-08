from setuptools import setup
import quamash
import re

groups = re.findall(r'(.+?) <(.+?)>(?:,\s*)?', quamash.__author__)
authors = [x[0].strip() for x in groups]
emails = [x[1].strip() for x in groups]
setup(
	name='Quamash',
	version=quamash.__version__,
	url='https://github.com/harvimt/quamash',
	author=', '.join(authors),
	author_email=', '.join(emails),
	packages=['quamash', ],
	license=quamash.__license__,
	description=quamash.__doc__,
	long_description=open('README').read(),
	keywords=['Qt', 'asyncio'],
	classifiers=[
		'License :: OSI Approved :: BSD License',
		'Operating System :: Microsoft :: Windows',
		'Operating System :: MacOS :: MacOS X',
		'Operating System :: POSIX',
		'Programming Language :: Python :: 3.4',
		'Environment :: X11 Applications :: Qt',
	],
)
