# DO NOT EDIT THIS FILE!
#
# This file is generated from the CDP specification. If you need to make
# changes, edit the generator and regenerate all of the modules.
#
# CDP domain: Media (experimental)

from __future__ import annotations
from cdp.util import event_class, T_JSON_DICT
from dataclasses import dataclass
import enum
import typing


class PlayerId(str):
    r'''
    Players will get an ID that is unique within the agent context.
    '''
    def to_json(self) -> str:
        return self

    @classmethod
    def from_json(cls, json: str) -> PlayerId:
        return cls(json)

    def __repr__(self):
        return 'PlayerId({})'.format(super().__repr__())


class Timestamp(float):
    def to_json(self) -> float:
        return self

    @classmethod
    def from_json(cls, json: float) -> Timestamp:
        return cls(json)

    def __repr__(self):
        return 'Timestamp({})'.format(super().__repr__())


@dataclass
class PlayerMessage:
    r'''
    Have one type per entry in MediaLogRecord::Type
    Corresponds to kMessage
    '''
    #: Keep in sync with MediaLogMessageLevel
    #: We are currently keeping the message level 'error' separate from the
    #: PlayerError type because right now they represent different things,
    #: this one being a DVLOG(ERROR) style log message that gets printed
    #: based on what log level is selected in the UI, and the other is a
    #: representation of a media::PipelineStatus object. Soon however we're
    #: going to be moving away from using PipelineStatus for errors and
    #: introducing a new error type which should hopefully let us integrate
    #: the error log level into the PlayerError type.
    level: str

    message: str

    def to_json(self) -> T_JSON_DICT:
        json: T_JSON_DICT = dict()
        json['level'] = self.level
        json['message'] = self.message
        return json

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerMessage:
        return cls(
            level=str(json['level']),
            message=str(json['message']),
        )


@dataclass
class PlayerProperty:
    r'''
    Corresponds to kMediaPropertyChange
    '''
    name: str

    value: str

    def to_json(self) -> T_JSON_DICT:
        json: T_JSON_DICT = dict()
        json['name'] = self.name
        json['value'] = self.value
        return json

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerProperty:
        return cls(
            name=str(json['name']),
            value=str(json['value']),
        )


@dataclass
class PlayerEvent:
    r'''
    Corresponds to kMediaEventTriggered
    '''
    timestamp: Timestamp

    value: str

    def to_json(self) -> T_JSON_DICT:
        json: T_JSON_DICT = dict()
        json['timestamp'] = self.timestamp.to_json()
        json['value'] = self.value
        return json

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerEvent:
        return cls(
            timestamp=Timestamp.from_json(json['timestamp']),
            value=str(json['value']),
        )


@dataclass
class PlayerError:
    r'''
    Corresponds to kMediaError
    '''
    type_: str

    #: When this switches to using media::Status instead of PipelineStatus
    #: we can remove "errorCode" and replace it with the fields from
    #: a Status instance. This also seems like a duplicate of the error
    #: level enum - there is a todo bug to have that level removed and
    #: use this instead. (crbug.com/1068454)
    error_code: str

    def to_json(self) -> T_JSON_DICT:
        json: T_JSON_DICT = dict()
        json['type'] = self.type_
        json['errorCode'] = self.error_code
        return json

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerError:
        return cls(
            type_=str(json['type']),
            error_code=str(json['errorCode']),
        )


def enable() -> typing.Generator[T_JSON_DICT,T_JSON_DICT,None]:
    r'''
    Enables the Media domain
    '''
    cmd_dict: T_JSON_DICT = {
        'method': 'Media.enable',
    }
    json = yield cmd_dict


def disable() -> typing.Generator[T_JSON_DICT,T_JSON_DICT,None]:
    r'''
    Disables the Media domain.
    '''
    cmd_dict: T_JSON_DICT = {
        'method': 'Media.disable',
    }
    json = yield cmd_dict


@event_class('Media.playerPropertiesChanged')
@dataclass
class PlayerPropertiesChanged:
    r'''
    This can be called multiple times, and can be used to set / override /
    remove player properties. A null propValue indicates removal.
    '''
    player_id: PlayerId
    properties: typing.List[PlayerProperty]

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerPropertiesChanged:
        return cls(
            player_id=PlayerId.from_json(json['playerId']),
            properties=[PlayerProperty.from_json(i) for i in json['properties']]
        )


@event_class('Media.playerEventsAdded')
@dataclass
class PlayerEventsAdded:
    r'''
    Send events as a list, allowing them to be batched on the browser for less
    congestion. If batched, events must ALWAYS be in chronological order.
    '''
    player_id: PlayerId
    events: typing.List[PlayerEvent]

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerEventsAdded:
        return cls(
            player_id=PlayerId.from_json(json['playerId']),
            events=[PlayerEvent.from_json(i) for i in json['events']]
        )


@event_class('Media.playerMessagesLogged')
@dataclass
class PlayerMessagesLogged:
    r'''
    Send a list of any messages that need to be delivered.
    '''
    player_id: PlayerId
    messages: typing.List[PlayerMessage]

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerMessagesLogged:
        return cls(
            player_id=PlayerId.from_json(json['playerId']),
            messages=[PlayerMessage.from_json(i) for i in json['messages']]
        )


@event_class('Media.playerErrorsRaised')
@dataclass
class PlayerErrorsRaised:
    r'''
    Send a list of any errors that need to be delivered.
    '''
    player_id: PlayerId
    errors: typing.List[PlayerError]

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayerErrorsRaised:
        return cls(
            player_id=PlayerId.from_json(json['playerId']),
            errors=[PlayerError.from_json(i) for i in json['errors']]
        )


@event_class('Media.playersCreated')
@dataclass
class PlayersCreated:
    r'''
    Called whenever a player is created, or when a new agent joins and receives
    a list of active players. If an agent is restored, it will receive the full
    list of player ids and all events again.
    '''
    players: typing.List[PlayerId]

    @classmethod
    def from_json(cls, json: T_JSON_DICT) -> PlayersCreated:
        return cls(
            players=[PlayerId.from_json(i) for i in json['players']]
        )