foo = dict(samuel=39, carrie=47, taylor=10)
foo['Ralph'] = {'age': 84, 'fun': 'yes'}


def print_age(taylor: dict, carrie: dict, **kwargs):
    print(taylor)
    print(carrie)
    bang = locals()
    print(bang)
    return {"taylor": 11, "samuel": 40, "alex": 4}


def bar(**kwargs):
    print(f"Show me the {kwargs}")


print(foo)
baz = print_age(**foo)
foo.update(**baz)

if "alex" in foo:
    bar(**foo)


with open("/home/samuel/Projects/iDRAC-Redfish-Scripting/redfish_python_async/ImportSystemConfigurationLocalFilenameREDFISH.py") as foo['file']:
    print(foo['file'].read())
