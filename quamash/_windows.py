import _winapi
import asyncio
from asyncio import windows_events

baseclass = asyncio.ProactorEventLoop

@with_logger
class IocpProactor(windows_events.IocpProactor):
    def __init__(self):
        self.__events = []
        super(IocpProactor, self).__init__()

    def select(self, timeout=None):
        """Override in order to handle events in a threadsafe manner."""
        if not self.__events:
            self._poll(timeout)
        tmp = self.__events
        self.__events = []
        return tmp

    def close(self):
        self._logger.debug('Closing')
        super(IocpProactor, self).close()

    def _poll(self, timeout=None):
        """Override in order to handle events in a threadsafe manner."""
        import math
        from asyncio import _overlapped
        INFINITE = 0xffffffff

        if timeout is None:
            ms = INFINITE
        elif timeout < 0:
            raise ValueError("negative timeout")
        else:
            # GetQueuedCompletionStatus() has a resolution of 1 millisecond,
            # round away from zero to wait *at least* timeout seconds.
            ms = math.ceil(timeout * 1e3)
            if ms >= INFINITE:
                raise ValueError("timeout too big")

        while True:
            self._logger.debug('Polling IOCP with timeout {} ms in thread {}...'.format(
                ms, threading.get_ident()))
            status = _overlapped.GetQueuedCompletionStatus(self._iocp, ms)

            if status is None:
                break
            err, transferred, key, address = status
            try:
                f, ov, obj, callback = self._cache.pop(address)
            except KeyError:
                # key is either zero, or it is used to return a pipe
                # handle which should be closed to avoid a leak.
                if key not in (0, _overlapped.INVALID_HANDLE_VALUE):
                    _winapi.CloseHandle(key)
                ms = 0
                continue

            if obj in self._stopped_serving:
                f.cancel()
            elif not f.cancelled():
                self.__events.append((f, callback, transferred, key, ov))

            ms = 0
