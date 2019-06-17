'''
DO NOT EDIT THIS FILE

This file is generated from the CDP definitions. If you need to make changes,
edit the generator and regenerate all of the modules.

Domain: input
Experimental: False
'''

from dataclasses import dataclass, field
import typing



class GestureSourceType:
    DEFAULT = "default"
    TOUCH = "touch"
    MOUSE = "mouse"

class TimeSinceEpoch(float):
    '''
    UTC time in seconds, counted from January 1, 1970.
    '''
    @classmethod
    def from_response(cls, response):
        return cls(response)

    def __repr__(self):
        return 'TimeSinceEpoch({})'.format(float.__repr__(self))



@dataclass
class TouchPoint:
    #: X coordinate of the event relative to the main frame's viewport in CSS pixels.
    x: float

    #: Y coordinate of the event relative to the main frame's viewport in CSS pixels. 0 refers to
    #: the top of the viewport and Y increases as it proceeds towards the bottom of the viewport.
    y: float

    #: X radius of the touch area (default: 1.0).
    radius_x: float

    #: Y radius of the touch area (default: 1.0).
    radius_y: float

    #: Rotation angle (default: 0.0).
    rotation_angle: float

    #: Force (default: 1.0).
    force: float

    #: Identifier used to track touch sources between events, must be unique within an event.
    id: float

    @classmethod
    def from_response(cls, response):
        return cls(
            x=float(response.get('x')),
            y=float(response.get('y')),
            radius_x=float(response.get('radiusX')),
            radius_y=float(response.get('radiusY')),
            rotation_angle=float(response.get('rotationAngle')),
            force=float(response.get('force')),
            id=float(response.get('id')),
        )
