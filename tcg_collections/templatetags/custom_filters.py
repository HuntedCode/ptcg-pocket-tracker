from django import template

register = template.Library()

@register.filter
def get_value(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_index(value, index):
    return value[index]

@register.filter
def startswith(text, starts):
    if isinstance(text, str):
        return text.startswith(starts)
    return False

@register.filter
def times(value):
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)

@register.filter
def div(value, divisor):
    return value / divisor

@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})