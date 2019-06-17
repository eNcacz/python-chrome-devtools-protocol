'''
DO NOT EDIT THIS FILE

This file is generated from the CDP definitions. If you need to make changes,
edit the generator and regenerate all of the modules.

Domain: tracing
Experimental: True
'''

from dataclasses import dataclass, field
import typing

from .types import *
from ..io import types as io



@dataclass
class BufferUsage:
    percent_full: float

    event_count: float

    value: float


@dataclass
class DataCollected:
    '''
    Contains an bucket of collected trace events. When tracing is stopped collected events will be
    send as a sequence of dataCollected events followed by tracingComplete event.
    '''
    #: Contains an bucket of collected trace events. When tracing is stopped collected events will be
    #: send as a sequence of dataCollected events followed by tracingComplete event.
    value: typing.List


@dataclass
class TracingComplete:
    '''
    Signals that tracing is stopped and there is no trace buffers pending flush, all data were
    delivered via dataCollected events.
    '''
    #: Signals that tracing is stopped and there is no trace buffers pending flush, all data were
    #: delivered via dataCollected events.
    stream: io.StreamHandle

    #: Signals that tracing is stopped and there is no trace buffers pending flush, all data were
    #: delivered via dataCollected events.
    trace_format: StreamFormat

    #: Signals that tracing is stopped and there is no trace buffers pending flush, all data were
    #: delivered via dataCollected events.
    stream_compression: StreamCompression
