from dataclasses import dataclass
from enum import Enum
import itertools
import json
import logging
import operator
import os
from pathlib import Path
from textwrap import dedent, indent as tw_indent
import typing

import inflection


log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'info').upper())
logging.basicConfig(level=log_level)
logger = logging.getLogger('generate')

SHARED_HEADER = '''DO NOT EDIT THIS FILE

This file is generated from the CDP specification. If you need to make changes,
edit the generator and regenerate all of the modules.'''

INIT_HEADER = '''\'\'\'
{}
\'\'\'

'''.format(SHARED_HEADER)

MODULE_HEADER = '''\'\'\'
{}

Domain: {{}}
Experimental: {{}}
\'\'\'

from cdp.util import event_class, T_JSON_DICT
from dataclasses import dataclass
import enum
import typing


'''.format(SHARED_HEADER)


def indent(s: str, n: int):
    ''' A shortcut for ``textwrap.indent`` that always uses spaces. '''
    return tw_indent(s, n * ' ')

def clear_dirs(package_path: Path):
    ''' Remove generated code. '''
    def rmdir(path):
        for subpath in path.iterdir():
            if subpath.is_file():
                subpath.unlink()
            elif subpath.is_dir():
                rmdir(subpath)
        path.rmdir()

    try:
        (package_path / '__init__.py').unlink()
    except FileNotFoundError:
        pass

    for subpath in package_path.iterdir():
        if subpath.is_dir():
            rmdir(subpath)


def inline_doc(description) -> str:
    ''' Generate an inline doc, e.g. ``#: This type is a ...`` '''
    if not description:
        return ''

    lines = ['#: {}\n'.format(l) for l in description.split('\n')]
    return ''.join(lines)


def docstring(description: typing.Optional[str]) -> str:
    ''' Generate a docstring from a description. '''
    if not description:
        return ''

    return dedent("'''\n{}\n'''").format(description)


def ref_to_python(ref: str) -> str:
    '''
    Convert a CDP ``$ref`` to the name of a Python type.

    For a dotted ref, the part before the dot is snake cased.
    '''
    if '.' in ref:
        domain, subtype = ref.split('.')
        ref = '{}.{}'.format(inflection.underscore(domain), subtype)
    return f"{ref}"


class CdpPrimitiveType(Enum):
    ''' All of the CDP types that map directly to a Python type. '''
    any = 'typing.Any'
    boolean = 'bool'
    integer = 'int'
    number = 'float'
    object = 'dict'
    string = 'str'


@dataclass
class CdpItems:
    ''' Represents the type of a repeated item. '''
    type: str
    ref: str

    @classmethod
    def from_json(cls, type) -> 'CdpItems':
        return cls(type.get('type'), type.get('$ref'))


@dataclass
class CdpProperty:
    ''' A property belonging to a non-primitive CDP type. '''
    name: str
    description: str
    type: str
    ref: str
    enum: typing.List[str]
    items: CdpItems
    optional: bool

    @property
    def py_name(self) -> str:
        ''' Get this property's Python name. '''
        return inflection.underscore(self.name)

    @property
    def py_annotation(self) -> str:
        ''' This property's Python type annotation. '''
        if self.items:
            if self.items.ref:
                py_ref = ref_to_python(self.items.ref)
                ann = "typing.List['{}']".format(py_ref)
            else:
                ann = 'typing.List[{}]'.format(
                    CdpPrimitiveType[self.items.type].value)
        else:
            if self.ref:
                py_ref = ref_to_python(self.ref)
                ann = f"'{py_ref}'"
            else:
                ann = CdpPrimitiveType[self.type].value
        if self.optional:
            ann = f'typing.Optional[{ann}]'
        return ann

    @classmethod
    def from_json(cls, property) -> 'CdpProperty':
        ''' Instantiate a CDP property from a JSON object. '''
        return cls(
            property['name'],
            property.get('description'),
            property.get('type'),
            property.get('$ref'),
            property.get('enum'),
            CdpItems.from_json(property['items']) if 'items' in property else None,
            property.get('optional', False),
        )

    def generate_decl(self) -> str:
        ''' Generate the code that declares this property. '''
        code = inline_doc(self.description)
        # todo handle dependencies later
        # elif '$ref' in prop and '.' not in prop_ann:
        #     # If the type lives in this module and is not a type that refers
        #     # to itself, then add it to the set of children so that
        #     # inter-class dependencies can be resolved later on.
        #     children.add(prop_ann)
        code += f'{self.py_name}: {self.py_annotation}'
        if self.optional:
            code += ' = None'
        return code

    def generate_to_json(self, dict_: str, use_self: bool=True) -> str:
        ''' Generate the code that exports this property to the specified JSON
        dict. '''
        self_ref = 'self.' if use_self else ''
        assign = f"{dict_}['{self.name}'] = "
        if self.items:
            if self.items.ref:
                assign += f"[i.to_json() for i in {self_ref}{self.py_name}]"
            else:
                assign += f"[i for i in {self_ref}{self.py_name}]"
        else:
            if self.ref:
                assign += f"{self_ref}{self.py_name}.to_json()"
            else:
                assign += f"{self_ref}{self.py_name}"
        if self.optional:
            code = dedent(f'''\
                if {self_ref}{self.py_name} is not None:
                    {assign}''')
        else:
            code = assign
        return code

    def generate_from_json(self, dict_='json') -> str:
        ''' Generate the code that creates an instance from a JSON dict named
        ``json``. '''
        # todo this is one of the few places where a real dependency is created
        # (most of the deps are type annotations and can be avoided by quoting
        # the annotation)
        if self.items:
            if self.items.ref:
                py_ref = ref_to_python(self.items.ref)
                expr = f"[{py_ref}.from_json(i) for i in {dict_}['{self.name}']]"
            else:
                py_type = CdpPrimitiveType[self.items.type].value
                expr = f"[{py_type}(i) for i in {dict_}['{self.name}']]"
        else:
            if self.ref:
                py_ref = ref_to_python(self.ref)
                expr = f"{py_ref}.from_json({dict_}['{self.name}'])"
            else:
                expr = f"{dict_}['{self.name}']"
        if self.optional:
            expr = f"{expr} if '{self.name}' in {dict_} else None"
        return expr


@dataclass
class CdpType:
    ''' A top-level CDP type. '''
    id: str
    description: str
    type: str
    items: CdpItems
    enum: typing.List[str]
    properties: typing.List[CdpProperty]

    @classmethod
    def from_json(cls, type_) -> 'CdpType':
        ''' Instantiate a CDP type from a JSON object. '''
        return cls(
            type_['id'],
            type_.get('description'),
            type_['type'],
            CdpItems.from_json(type_['items']) if 'items' in type_ else None,
            type_.get('enum'),
            [CdpProperty.from_json(p) for p in type_.get('properties', list())],
        )

    def generate_code(self) -> str:
        ''' Generate Python code for this type. '''
        # todo handle exports and emitted types somewhere else?
        # exports = list()
        # exports.append(type_name)
        # emitted_types = set()
        logger.debug('Generating type %s: %s', self.id, self.type)
        if self.enum:
            return self.generate_enum_code()
        elif self.properties:
            return self.generate_class_code()
        else:
            return self.generate_primitive_code()

    def generate_primitive_code(self) -> str:
        ''' Generate code for a primitive type. '''
        if self.items:
            if self.items.ref:
                nested_type = ref_to_python(self.items.ref)
                py_type = f"typing.List['{nested_type}']"
            else:
                nested_type = CdpPrimitiveType[self.items.type].value
                py_type = f'typing.List[{nested_type}]'
            superclass = 'list'
        else:
            # A primitive type cannot have a ref, so there is no branch here.
            py_type = CdpPrimitiveType[self.type].value
            superclass = py_type

        code = f'class {self.id}({superclass}):\n'
        doc = docstring(self.description)
        if doc:
            code += indent(doc, 4) + '\n'

        def_to_json = dedent(f'''\
            def to_json(self) -> {py_type}:
                return self''')
        code += indent(def_to_json, 4)

        def_from_json = dedent(f'''\
            @classmethod
            def from_json(cls, json: {py_type}) -> '{self.id}':
                return cls(json)''')
        code += '\n\n' + indent(def_from_json, 4)

        def_repr = dedent(f'''\
            def __repr__(self):
                return '{self.id}({{}})'.format(super().__repr__())''')
        code += '\n\n' + indent(def_repr, 4)

        return code

    def generate_enum_code(self) -> str:
        '''
        Generate an "enum" type.

        Enums are handled by making a python class that contains only class
        members. Each class member is upper snaked case, e.g.
        ``MyTypeClass.MY_ENUM_VALUE`` and is assigned a string value from the
        CDP metadata.
        '''
        def_to_json = dedent('''\
            def to_json(self) -> str:
                return self.value''')

        def_from_json = dedent(f'''\
            @classmethod
            def from_json(cls, json: str) -> '{self.id}':
                return cls(json)''')

        code = f'class {self.id}(enum.Enum):\n'
        doc = docstring(self.description)
        if doc:
            code += indent(doc, 4) + '\n'
        for enum_member in self.enum:
            snake_case = inflection.underscore(enum_member).upper()
            enum_code = f'{snake_case} = "{enum_member}"\n'
            code += indent(enum_code, 4)
        code += '\n' + indent(def_to_json, 4)
        code += '\n\n' + indent(def_from_json, 4)

        return code

    def generate_class_code(self) -> str:
        '''
        Generate a class type.

        Top-level types that are defined as a CDP ``object`` are turned into Python
        dataclasses.
        '''
        # children = set()
        code = dedent(f'''\
            @dataclass
            class {self.id}:\n''')
        doc = docstring(self.description)
        if doc:
            code += indent(doc, 4) + '\n'

        # Emit property declarations. These are sorted so that optional
        # properties come after required properties, which is required to make
        # the dataclass constructor work.
        props = list(self.properties)
        props.sort(key=operator.attrgetter('optional'))
        code += '\n\n'.join(indent(p.generate_decl(), 4) for p in props)
        code += '\n\n'

        # Emit to_json() method. The properties are sorted in the same order as
        # above for readability.
        def_to_json = dedent('''\
            def to_json(self) -> T_JSON_DICT:
                json: T_JSON_DICT = dict()
        ''')
        assigns = (p.generate_to_json(dict_='json') for p in props)
        def_to_json += indent('\n'.join(assigns), 4)
        def_to_json += '\n'
        def_to_json += indent('return json', 4)
        code += indent(def_to_json, 4) + '\n\n'

        # Emit to_json() method. The properties are sorted in the same order as
        # above for readability.
        def_from_json = dedent(f'''\
            @classmethod
            def from_json(cls, json: T_JSON_DICT) -> '{self.id}':
                return cls(
        ''')
        def_from_json += indent('\n'.join(f'{p.name}={p.generate_from_json()},'
            for p in self.properties), 8)
        def_from_json += '\n'
        def_from_json += indent(')', 4)
        code += indent(def_from_json, 4)

        # todo we used to return a dict but i'm not sure if that's still needed?
        # return {
        #     'name': self.id,
        #     'code': code,
        #     Don't emit children that live in a different module. We assume that
        #     modules do not have cyclical dependencies on each other.
        #     'children': [c for c in children if '.' not in c],
        # }
        return code

    # Todo how to resolve dependencies?
    # The classes have dependencies on each other, so we have to emit them in
    # a specific order. If we can't resolve these dependencies after a certain
    # number of iterations, it suggests a cyclical dependency that this code
    # cannot handle.
    # tries_remaining = 1000
    # while classes:
    #     class_ = classes.pop(0)
    #     if not class_['children']:
    #         code += class_['code']
    #         emitted_types.add(class_['name'])
    #         continue
    #     if all(child in emitted_types for child in class_['children']):
    #         code += class_['code']
    #         emitted_types.add(class_['name'])
    #         continue
    #     classes.append(class_)
    #     tries_remaining -= 1
    #     if not tries_remaining:
    #         logger.error('Class resolution failed. Emitted these types: %s',
    #             emitted_types)
    #         logger.error('Class resolution failed. Cannot emit these types: %s',
    #             json.dumps(classes, indent=2))
    #         raise Exception('Failed to resolve class dependencies.'
    #             ' See output above.')


class CdpParameter(CdpProperty):
    ''' A parameter to a CDP command. '''
    def generate_code(self) -> str:
        ''' Generate the code for a parameter in a function call. '''
        if self.items:
            if self.items.ref:
                nested_type = ref_to_python(self.items.ref)
                py_type = f"typing.List['{nested_type}']"
            else:
                nested_type = CdpPrimitiveType[self.items.type].value
                py_type = f'typing.List[{nested_type}]'
        else:
            if self.ref:
                py_type = "'{}'".format(ref_to_python(self.ref))
            else:
                py_type = CdpPrimitiveType[self.type].value
        if self.optional:
            py_type = f'typing.Optional[{py_type}]'
        code = f"{self.py_name}: {py_type}"
        if self.optional:
            code += ' = None'
        return code

    def generate_decl(self) -> str:
        ''' Generate the declaration for this parameter. '''
        if self.description:
            code = inline_doc(self.description)
            code += '\n'
        else:
            code = ''
        code += f'{self.py_name}: {self.py_annotation}'
        return code

    def generate_doc(self) -> str:
        ''' Generate the docstring for this parameter. '''
        doc = f':param {self.py_name}:'
        if self.description:
            desc = self.description.replace('`', '``')
            doc += f' {desc}'
        return doc

    def generate_from_json(self, dict_) -> str:
        '''
        Generate the code to instantiate this parameter from a JSON dict.
        '''
        code = super().generate_from_json(dict_)
        try:
            prim = CdpPrimitiveType[self.type].value
            code = f'{prim}({code})'
        except KeyError:
            pass
        return f'{self.py_name}={code}'


class CdpReturn(CdpProperty):
    ''' A return value from a CDP command. '''
    @property
    def py_annotation(self):
        if self.items:
            if self.items.ref:
                py_ref = ref_to_python(self.items.ref)
                ann = f"typing.List['{py_ref}']"
            else:
                py_type = CdpPrimitiveType[self.items.type].value
                ann = f'typing.List[{py_type}]'
        else:
            if self.ref:
                py_ref = ref_to_python(self.ref)
                ann = f"'{py_ref}'"
            else:
                ann = CdpPrimitiveType[self.type].value

        return ann

    def generate_doc(self):
        ''' Generate the docstring for this return. '''
        if self.description:
            doc = self.description.replace('`', '``')
            if self.optional:
                doc = f'(Optional) {doc}'
        else:
            doc = ''
        return doc

    def generate_return(self, dict_):
        ''' Generate code for returning this value. '''
        code = super().generate_from_json()
        try:
            type_ = CdpPrimitiveType[self.type].value
            code = f'{type_}({code})'
        except:
            pass
        return code


@dataclass
class CdpCommand:
    ''' A CDP command. '''
    name: str
    description: str
    experimental: bool
    parameters: typing.List[CdpParameter]
    returns: typing.List[CdpReturn]
    domain: str

    @property
    def py_name(self):
        ''' Get a Python name for this command. '''
        return inflection.underscore(self.name)

    @classmethod
    def from_json(cls, command, domain) -> 'CdpCommand':
        ''' Instantiate a CDP command from a JSON object. '''
        parameters = command.get('parameters', list())
        returns = command.get('returns', list())

        return cls(
            command['name'],
            command.get('description'),
            command.get('experimental', False),
            [CdpParameter.from_json(p) for p in parameters],
            [CdpReturn.from_json(r) for r in returns],
            domain,
        )

    def generate_code(self) -> str:
        ''' Generate code for a CDP command. '''
        # Generate the function header
        if len(self.returns) == 0:
            ret_type = 'None'
        elif len(self.returns) == 1:
            ret_type = self.returns[0].py_annotation
        else:
            nested_types = ', '.join(r.py_annotation for r in self.returns)
            ret_type = f'typing.Tuple[{nested_types}]'
        ret_type = f"typing.Generator[T_JSON_DICT,T_JSON_DICT,{ret_type}]"
        code = f'def {self.py_name}('
        ret = f') -> {ret_type}:\n'
        if self.parameters:
            code += '\n'
            code += indent(
                ',\n'.join(p.generate_code() for p in self.parameters), 8)
            code += '\n'
            code += indent(ret, 4)
        else:
            code += ret

        # Generate the docstring
        if self.description:
            doc = self.description
        else:
            doc = ''
        if self.parameters and doc:
            doc += '\n\n'
        elif not self.parameters and self.returns:
            doc += '\n'
        doc += '\n'.join(p.generate_doc() for p in self.parameters)
        if len(self.returns) == 1:
            doc += '\n'
            ret_doc = self.returns[0].generate_doc()
            doc += f':returns: {ret_doc}'
        elif len(self.returns) > 1:
            doc += '\n'
            doc += ':returns: a tuple with the following items:\n'
            ret_docs = '\n'.join(f'{i}. {r.name}: {r.generate_doc()}' for i, r
                in enumerate(self.returns))
            doc += indent(ret_docs, 4)
        if doc:
            code += indent(docstring(doc), 4)

        # Generate the function body
        if self.parameters:
            code += '\n'
            code += indent('params: T_JSON_DICT = dict()', 4)
            code += '\n'
        assigns = (p.generate_to_json(dict_='params', use_self=False)
            for p in self.parameters)
        code += indent('\n'.join(assigns), 4)
        code += '\n'
        code += indent('cmd_dict: T_JSON_DICT = {\n', 4)
        code += indent(f"'method': '{self.domain}.{self.name}',\n", 8)
        if self.parameters:
            code += indent("'params': params,\n", 8)
        code += indent('}\n', 4)
        code += indent('json = yield cmd_dict', 4)
        if len(self.returns) == 0:
            pass
        else:
            code += '\n'
            expr = ', '.join(r.generate_return(dict_='json') for r in self.returns)
            code += indent(f'return {expr}', 4)
        return code


@dataclass
class CdpEvent:
    ''' A CDP event object. '''
    name: str
    description: str
    parameters: typing.List[CdpParameter]
    domain: str

    @property
    def py_name(self):
        ''' Return the Python class name for this event. '''
        return inflection.camelize(self.name, uppercase_first_letter=True)

    @classmethod
    def from_json(cls, json: dict, domain: str):
        ''' Create a new CDP event instance from a JSON dict. '''
        return cls(
            json['name'],
            json.get('description'),
            [CdpParameter.from_json(p) for p in json.get('parameters', list())],
            domain
        )

    def generate_code(self) -> str:
        ''' Generate code for a CDP event. '''
        code = dedent(f'''\
            @event_class('{self.domain}.{self.name}')
            @dataclass
            class {self.py_name}:''')
        code += '\n'
        if self.description:
            code += indent(docstring(self.description), 4)
            code += '\n'
        code += indent(
            '\n'.join(p.generate_decl() for p in self.parameters), 4)
        code += '\n\n'
        def_from_json = dedent(f'''\
            @classmethod
            def from_json(cls, json: T_JSON_DICT) -> '{self.py_name}':
                return cls(
        ''')
        code += indent(def_from_json, 4)
        from_json = ',\n'.join(p.generate_from_json(dict_='json')
            for p in self.parameters)
        code += indent(from_json, 12)
        code += '\n'
        code += indent(')', 8)
        return code


@dataclass
class CdpDomain:
    ''' A CDP domain contains metadata, types, commands, and events. '''
    domain: str
    experimental: bool
    dependencies: typing.List[str]
    types: typing.List[CdpType]
    commands: typing.List[CdpCommand]
    events: typing.List[CdpEvent]

    @property
    def module(self):
        ''' The name of the Python module for this CDP domain. '''
        return inflection.underscore(self.domain)

    @classmethod
    def from_json(cls, domain: dict):
        ''' Instantiate a CDP domain from a JSON object. '''
        types = domain.get('types', list())
        commands = domain.get('commands', list())
        events = domain.get('events', list())
        domain_name = domain['domain']

        return cls(
            domain_name,
            domain.get('experimental', False),
            domain.get('dependencies', list()),
            [CdpType.from_json(type) for type in types],
            [CdpCommand.from_json(command, domain_name)
                for command in commands],
            [CdpEvent.from_json(event, domain_name) for event in events]
        )

    def generate_code(self) -> str:
        ''' Generate the Python module code for a given CDP domain. '''
        code = MODULE_HEADER.format(self.domain, self.experimental)
        item_iter = itertools.chain(
            iter(self.types),
            iter(self.commands),
            iter(self.events),
        )
        code += '\n\n\n'.join(item.generate_code() for item in item_iter)
        code += '\n'
        return code

        # todo update dependencies
        # The dependencies listed in the JSON don't match the actual dependencies
        # encountered when building the types. So we ignore the declared
        # dependencies and compute it ourself.
        # type_dependencies = set()
        # domain_types = domain.get('types', list())
        # for type_ in domain_types:
        #     for prop in type_.get('properties', list()):
        #         dependency = get_dependency(prop)
        #         if dependency:
        #             type_dependencies.add(dependency)
        # if type_dependencies:
        #     logger.debug('Computed type_dependencies: %s', ','.join(
        #         type_dependencies))
        #
        # event_dependencies = set()
        # domain_events = domain.get('events', list())
        # for event in domain_events:
        #     for param in event.get('parameters', list()):
        #         dependency = get_dependency(param)
        #         if dependency:
        #             event_dependencies.add(dependency)
        # if event_dependencies:
        #     logger.debug('Computed event_dependencies: %s', ','.join(
        #         event_dependencies))
        #
        # command_dependencies = set()
        # domain_commands = domain.get('commands', list())
        # for command in domain_commands:
        #     for param in command.get('parameters', list()):
        #         dependency = get_dependency(param)
        #         if dependency:
        #             command_dependencies.add(dependency)
        #     for return_ in command.get('returns', list()):
        #         dependency = get_dependency(return_)
        #         if dependency:
        #             command_dependencies.add(dependency)
        # if command_dependencies:
        #     logger.debug('Computed command_dependencies: %s', ','.join(
        #         command_dependencies))

        # types_path = module_path / 'types.py'
        # with types_path.open('w') as types_file:
        #     types_file.write(module_header.format(module_name, self.experimental))
        #     for dependency in sorted(type_dependencies):
        #         types_file.write(import_dependency(dependency))
        #     if type_dependencies:
        #         types_file.write('\n')
        #     type_exports, type_code = generate_types(domain_types)
        #     types_file.write(type_code)
        #
        # events_path = module_path / 'events.py'
        # with events_path.open('w') as events_file:
        #     events_file.write(module_header.format(module_name, self.experimental))
        #     events_file.write('from .types import *\n')
        #     for dependency in sorted(event_dependencies):
        #         events_file.write(import_dependency(dependency))
        #     if event_dependencies:
        #         events_file.write('\n')
        #     event_exports, event_code = generate_events(self.domain, domain_events)
        #     events_file.write(event_code)
        #
        # commands_path = module_path / 'commands.py'
        # with commands_path.open('w') as commands_file:
        #     commands_file.write(module_header.format(module_name, self.experimental))
        #     commands_file.write('from .types import *\n')
        #     for dependency in sorted(command_dependencies):
        #         commands_file.write(import_dependency(dependency))
        #     if command_dependencies:
        #         commands_file.write('\n')
        #     command_exports, command_code = generate_commands(self.domain, domain_commands)
        #     commands_file.write(command_code)

        # return module_name, type_exports, event_exports, command_exports


def parse(json_path, output_path):
    '''
    Parse JSON protocol description and return domain objects.

    :param Path json_path: path to a JSON CDP schema
    :param Path output_path: a directory path to create the modules in
    :returns: a list of CDP domain objects
    '''
    with json_path.open() as json_file:
        schema = json.load(json_file)
    version = schema['version']
    assert (version['major'], version['minor']) == ('1', '3')
    domains = list()
    for domain in schema['domains']:
        domains.append(CdpDomain.from_json(domain))
    return domains


def generate_init(init_path, domains):
    '''
    Generate an ``__init__.py`` that exports the specified modules.

    :param Path init_path: a file path to create the init file in
    :param list[tuple] modules: a list of modules each represented as tuples
        of (name, list_of_exported_symbols)
    '''
    with init_path.open('w') as init_file:
        init_file.write(INIT_HEADER)
        init_file.write('import cdp.util\n\n')
        for domain in domains:
            init_file.write('import cdp.{}\n'.format(domain.module))


def main():
    ''' Main entry point. '''
    here = Path(__file__).parent.resolve()
    json_paths = [
        here / 'browser_protocol.json',
        here / 'js_protocol.json',
    ]
    output_path = here.parent / 'cdp'
    output_path.mkdir(exist_ok=True)
    clear_dirs(output_path)

    domains = list()
    for json_path in json_paths:
        logger.info('Parsing JSON file %s', json_path)
        domains.extend(parse(json_path, output_path))
    domains.sort(key=operator.attrgetter('domain'))

    for domain in domains:
        logger.info('Generating module: %s → %s.py', domain.domain,
            domain.module)
        module_path = output_path / f'{domain.module}.py'
        with module_path.open('w') as module_file:
            module_file.write(domain.generate_code())

    init_path = output_path / '__init__.py'
    generate_init(init_path, domains)

    py_typed_path = output_path / 'py.typed'
    py_typed_path.touch()


if __name__ == '__main__':
    main()
