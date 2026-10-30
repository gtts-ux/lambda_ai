"""Family/version navigation using catalog IDs, without loading model weights."""
import re

class ModelBrowser:
    def __init__(self,manager):
        self.manager=manager;self.family=None;self.index=0

    def families(self):
        groups={}
        for entry in self.manager.entries():
            match=re.match(r'lambda-(\d+)',entry['id'])
            family=match.group(1) if match else 'other'
            groups.setdefault(family,[]).append(entry)
        return groups

    def rows(self):
        groups=self.families()
        if self.family is None:
            return [{'id':key,'name':'lambda '+key if key!='other' else 'Other models','versions':versions}
                    for key,versions in sorted(groups.items(),key=lambda p:int(p[0]) if p[0].isdigit() else 100000)]
        return groups.get(self.family,[])

    def move(self,delta):
        rows=self.rows()
        self.index=max(0,min(len(rows)-1,self.index+delta)) if rows else 0

    def choose(self,index=None):
        rows=self.rows();index=self.index if index is None else index
        if not 0<=index<len(rows):raise ValueError('Choose a listed family or model.')
        self.index=index
        if self.family is None:
            self.family=rows[index]['id'];self.index=0;return None
        return 'use:'+rows[index]['id']

    def back(self):
        family=self.family
        if family is not None:
            self.family=None
            self.index=next((i for i,row in enumerate(self.rows()) if row['id']==family),0)
            return True
        return False

    def text(self,active_id):
        lines=['MODELS / '+('FAMILIES' if self.family is None else 'LAMBDA '+self.family+' VERSIONS'),'',
               '  ↑/↓ select · Enter/→ open or use · ←/Esc back','']
        for i,row in enumerate(self.rows()):
            marker='›' if i==self.index else ' '
            if self.family is None:
                versions=' · '.join(e['name'].removeprefix('lambda ') for e in row['versions'])
                lines.append(f" {marker} {i+1}. {row['name']}    {versions}")
            else:
                status='active' if row['id']==active_id else 'installed' if row['installed_revision'] else 'download'
                lines.append(f" {marker} {i+1}. {row['name']}    [{status}]")
                lines.append(f"       {row['bytes']/1048576:.1f} MiB · app ≥ {row['min_app_version']}")
        return '\n'.join(lines)
