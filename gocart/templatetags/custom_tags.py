# gocart/templatetags/custom_tags.py

from django import template

register = template.Library()

@register.filter
def dictkey(value, key):
    return value.get(key)
