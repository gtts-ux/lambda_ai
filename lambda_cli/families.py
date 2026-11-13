"""Display families and compatible aliases; model files and legacy IDs stay intact."""
import re

ORDER={'mercury':1,'venus':2,'code':3,'terra':4,'other':99}

def canonical_id(identifier):
    for family in ('mercury','venus'):
        prefix='lambda-'+family+'-'
        if identifier and identifier.startswith(prefix):
            version=identifier[len(prefix):]
            expected='1' if family=='mercury' else '2'
            if re.fullmatch(expected+r'(?:\.\d+)*',version):return 'lambda-'+version
    return identifier

def family_for(identifier):
    if identifier.startswith('lambda-code-'):return 'code'
    if identifier.startswith('lambda-terra-'):return 'terra'
    match=re.match(r'lambda-(\d+)(?:\.|$)',canonical_id(identifier))
    return {'1':'mercury','2':'venus','3':'code','4':'terra'}.get(match.group(1),'other') if match else 'other'

def display_name(identifier,name):
    family=family_for(identifier or '')
    if family in ('mercury','venus'):
        version=canonical_id(identifier).removeprefix('lambda-')
        return f'lambda {family} {version}'
    return name
