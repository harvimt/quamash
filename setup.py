from distutils.core import setup
import quamash
import re


groups = re.findall(r'(.+?) <(.+?)>(?:,\s*)?', quamash.__author__)
authors = [x[0].strip() for x in groups]
emails = [x[1].strip() for x in groups]
setup(
    name='Quamash',
    version=quamash.__version__,
    author=', '.join(authors),
    author_email=', '.join(emails),
    packages=['quamash', ],
    license=quamash.__license__,
    description=quamash.__doc__,
    long_description=open('README').read(),
)
