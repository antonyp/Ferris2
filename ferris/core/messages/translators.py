import inspect
import copy
from protorpc import messages
from .converters import converters as default_converters
from ..bunch import Bunch


def _common_fields(entity, message):
    message_fields = [x.name for x in message.all_fields()]
    entity_properties = [k for k, v in entity._properties.iteritems()]
    fields = set(message_fields) & set(entity_properties)
    return message_fields, entity_properties, fields


def entity_to_message(entity, message, converters=None):
    message_fields, entity_properties, fields = _common_fields(entity, message)

    converters = dict(default_converters.items() + converters.items()) if converters else default_converters

    # Key first
    values = {
        'key': converters['Key'].to_message(entity, 'key', 'key', entity.key) if entity.key else None
    }

    # Other fields
    for field in fields:
        property = entity._properties[field]
        message_field = message.field_by_name(field)
        value = getattr(entity, field)

        converter = converters[property.__class__]

        if converter:
            if value:  # only try to convert if the value is meaningful, otherwise leave it as Falsy.
                if property._repeated:
                    value = [converter.to_message(entity, property, message_field, x) if x else x for x in value]
                else:
                    value = converter.to_message(entity, property, message_field, value)
            values[field] = value

    if inspect.isclass(message):
        return message(**values)
    else:
        for name, value in values.iteritems():
            setattr(message, name, value)
        return message


def message_to_entity(message, model, converters=None):
    message_fields, entity_properties, fields = _common_fields(model, message)

    converters = dict(default_converters.items() + converters.items()) if converters else default_converters

    values = {}

    # Key first, if it's there
    if hasattr(message, 'key') and message.key:
        values['key'] = converters['Key'].to_model(messages, 'key', 'key', message.key) if message.key else None

    # Other fields
    for field in fields:
        property = model._properties[field]
        message_field = message.field_by_name(field)
        value = getattr(message, field)

        converter = converters[property.__class__]

        if value and converter:
            if property._repeated:
                value = [converter.to_model(message, property, message_field, x) if x else x for x in value]
            else:
                value = converter.to_model(message, property, message_field, value)
            values[field] = value

    if inspect.isclass(model):
        return model(**values)
    else:
        model.populate(**values)
        return model


def model_message(Model, only=None, exclude=None, converters=None):
    name = Model.__name__ + 'Message'

    props = Model._properties
    sorted_props = sorted(props.iteritems(), key=lambda prop: prop[1]._creation_counter)
    field_names = [x[0] for x in sorted_props if x[0]]

    if exclude:
        field_names = [x for x in field_names if x not in exclude]

    if only:
        field_names = [x for x in field_names if x in only]

    converters = dict(default_converters.items() + converters.items()) if converters else default_converters

    # Add in the key field.
    field_dict = {
        'key': converters['Key'].to_field(Model, Bunch(name='key', _repeated=False), 1)
    }

    # Add all other fields.
    for count, name in enumerate(field_names, start=2):
        prop = props[name]
        converter = converters.get(prop.__class__, None)

        if converter:
            field_dict[name] = converter.to_field(Model, prop, count)

    return type(name, (messages.Message,), field_dict)


def list_message(message_type):
    name = message_type.__name__ + 'List'
    fields = {
        'items': messages.MessageField(message_type, 1, repeated=True),
    }
    return type(name, (messages.Message,), fields)


def compose(*args):
    fields = {}
    name = 'Composed'

    for message_cls in args:
        name += message_cls.__name__
        for field in message_cls.all_fields():
            fields[field.name] = field

    for n, orig_field in enumerate(fields.values(), 1):
        field = copy.copy(orig_field)
        # This is so ridiculously hacky. I'm not proud of it, but the alternative to doing this is trying to reconstruct each
        # field by figuring out the arguments originally passed into __init__. I think this is honestly a little cleaner.
        object.__setattr__(field, 'number', n)
        fields[field.name] = field

    return type(name, (messages.Message,), fields)
