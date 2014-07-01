import asyncio
from asyncio import selectors

baseclass = asyncio.SelectorEventLoop

selector_cls = selectors.DefaultSelector
