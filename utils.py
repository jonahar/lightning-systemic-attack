import json

from datatypes import Json


def print_json(o: Json):
    print(json.dumps(o, indent=4))
