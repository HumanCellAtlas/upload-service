import re


class MediaType:

    RFC7320_TOKEN_CHARSET = "!#$%&'*+-.^_`|~\w"

    @classmethod
    def from_string(cls, media_type):
        split_on_semicolons = media_type.split(';')
        type_info = split_on_semicolons.pop(0)
        type_info = re.match("(?P<top_level_type>.+)/(?P<subtype>[^+]+)(?P<suffix>\+.+)?", type_info)
        parameters = {}
        for parameter in split_on_semicolons:
            param_match = re.match('(.+)=(.+)', parameter.strip())
            parameters[param_match[1]] = param_match[2].strip('"')
        return cls(type_info['top_level_type'], type_info['subtype'], suffix=type_info['suffix'], parameters=parameters)

    def __init__(self, top_level_type, subtype, suffix=None, parameters={}):
        self.top_level_type = top_level_type
        self.subtype = subtype
        self.suffix = suffix
        self.parameters = parameters

    def __str__(self):
        media_type = "{type}/{subtype}".format(type=self.top_level_type, subtype=self.subtype)
        if self.suffix:
            media_type += self.suffix
        if self.parameters:
            for k, v in self.parameters.items():
                media_type += '; {key}={value}'.format(key=k, value=self._properly_quoted_parameter_value(v))
        return media_type

    def _properly_quoted_parameter_value(self, value):
        """
        Per RFC 7321 (https://tools.ietf.org/html/rfc7231#section-3.1.1.1):
        Parameters values don't need to be quoted if they are a "token".
        Token characters are defined by RFC 7320 (https://tools.ietf.org/html/rfc7230#section-3.2.6).
        Otherwise, parameters values can be a "quoted-string".
        So we will quote values that contain characters other than the standard token characters.
        """
        if re.match(f"^[{self.RFC7320_TOKEN_CHARSET}]*$", value):
            return value
        else:
            return f'"{value}"'
