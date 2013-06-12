from distutils.core import setup
import quamash
import re
author = re.match(r'(?P<name>[^<]* <(?P<email>.*)>', quamash.__author__)

setup(
    name='Quamash',
    version=quamash.__version__,
    author=author.group('name'),
    author_email=author.group('email'),
    packages=['quamash', ],
    license=quamash.__license__,
    depends=['tulip', 'PyQt', ],
    description=quamash.__doc__,
    long_description=open('README').read(),
)
