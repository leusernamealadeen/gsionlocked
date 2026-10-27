"""Build the pinned HyperOS ART RPC candidate against captured Samsung ART. No deployment."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,os,re,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
GUEST_DEFAULT='24bd859f09fcfbe9f07be85a97147dc57b70667849aac67162b99ea132b13543'
HOST_DEFAULT='17d44eafadfae9616ff3a90620342933a14531eb1c924523b4dc40ed2893139b'
WIRE=('ProfilePath','ProfilePath$WritableProfilePath','ProfilePath$PrimaryRefProfilePath','ProfilePath$PrimaryCurProfilePath','ProfilePath$SecondaryRefProfilePath','ProfilePath$SecondaryCurProfilePath','ProfilePath$PrebuiltProfilePath','ProfilePath$TmpProfilePath','DexMetadataPath','FsPermission','OutputProfile','OutputSecureDexMetadataCompanion','MergeProfileOptions','CopyAndRewriteProfileResult','GetDexoptStatusResult','ArtifactsPath','RuntimeArtifactsPath','SecureDexMetadataWithCompanionPaths','VdexPath')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def wire(text):
    m=re.search(r'^\.method public (?:final )?writeToParcel\(.*?^\.end method',text,re.M|re.S)
    if not m:raise ValueError('Parcel writer missing')
    return '\n'.join(line.strip() for line in m[0].splitlines() if line.strip() and not line.strip().startswith('.line'))

def status_fields(text):
    pattern=r'iget(?:-object|-boolean)? ([vp]\d+), p0, Lcom/android/server/art/GetDexoptStatusResult;->(\w+):([^\n]+)\ninvoke-virtual \{p1, \1\}, Landroid/os/Parcel;->(write\w+)\([^\n]+'
    return [(m[2],m[3],m[4]) for m in re.finditer(pattern,wire(text))]

def default_status_command(text):
    pattern=re.compile(r'(^\.method public constructor <init>\(\)V\n)(.*?)(^\.end method)',re.M|re.S)
    hits=list(pattern.finditer(text))
    if len(hits)!=1 or '.locals 1' not in hits[0][2] or hits[0][2].count('return-void')!=1:raise ValueError('Unexpected status parcel constructor')
    def changed(m):
        body=m[2].replace('    return-void','    const-string v0, ""\n    iput-object v0, p0, Lcom/android/server/art/GetDexoptStatusResult;->dex2oatCmdline:Ljava/lang/String;\n    return-void')
        return m[1]+body+m[3]
    return pattern.sub(changed,text)

def add_host_status_field(text):
    """Teach an older guest parcelable the S24 host's inserted ART string."""
    field='.field public imageLocationDebugString:Ljava/lang/String;'
    field_anchor='.field public isBackedByVdexOnly:Z'
    if field in text or text.count(field_anchor)!=1:raise ValueError('Unexpected GetDexoptStatusResult field set')
    text=text.replace(field_anchor,field_anchor+'\n\n'+field,1)
    read=re.compile(r'(    iput-boolean v2, p0, Lcom/android/server/art/GetDexoptStatusResult;->isBackedByVdexOnly:Z\n)(\n    \.line [0-9]+\n    invoke-virtual \{p1\}, Landroid/os/Parcel;->dataPosition\(\)I)')
    read_code=('\n    invoke-virtual {p1}, Landroid/os/Parcel;->readString()Ljava/lang/String;\n'
               '    move-result-object v2\n\n'
               '    iput-object v2, p0, Lcom/android/server/art/GetDexoptStatusResult;->imageLocationDebugString:Ljava/lang/String;')
    text,n=read.subn(r'\1'+read_code+r'\2',text,count=1)
    if n!=1:raise ValueError('Could not add host ART field to guest parcel reader')
    write=re.compile(r'(    invoke-virtual \{p1, v0\}, Landroid/os/Parcel;->writeBoolean\(Z\)V\n)(\n    \.line [0-9]+\n    iget p0, p0, Lcom/android/server/art/GetDexoptStatusResult;->artifactsLocation:I)')
    write_code=('\n    iget-object v0, p0, Lcom/android/server/art/GetDexoptStatusResult;->imageLocationDebugString:Ljava/lang/String;\n\n'
                '    invoke-virtual {p1, v0}, Landroid/os/Parcel;->writeString(Ljava/lang/String;)V')
    text,n=write.subn(r'\1'+write_code+r'\2',text,count=1)
    if n!=1:raise ValueError('Could not add host ART field to guest parcel writer')
    return text

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('guest-jar','host-jar','apktool','sdk','java-home','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--guest-sha256',default=GUEST_DEFAULT)
    p.add_argument('--host-sha256',default=HOST_DEFAULT)
    a=p.parse_args()
    if not re.fullmatch('[a-f0-9]{64}',a.guest_sha256) or not re.fullmatch('[a-f0-9]{64}',a.host_sha256):p.error('Expected SHA-256 input pins')
    if sha(a.guest_jar)!=a.guest_sha256 or sha(a.host_jar)!=a.host_sha256:p.error('Unexpected guest or host ART input')
    if a.output.exists():p.error('Existing output is preserved')
    a.output.mkdir(parents=True);out=a.output.resolve();exe='.exe' if os.name=='nt' else '';java=a.java_home.resolve()/'bin'/('java'+exe);javac=java.with_name('javac'+exe);apktool=a.apktool.resolve();sdk=a.sdk.resolve()
    def run(*args):subprocess.run([str(x) for x in args],check=True)
    for name,source in [('host',a.host_jar),('guest',a.guest_jar)]:run(java,'-jar',apktool,'d','-f','-r','-o',out/name,source.resolve())
    roots=[out/name/'smali/com/android/server/art' for name in ('host','guest')]
    status_field_adaptations=[]
    for name in WIRE:
        values=[wire((root/(name+'.smali')).read_text(encoding='utf-8')) for root in roots]
        if values[0]!=values[1]:
            if name!='GetDexoptStatusResult':raise ValueError('Incompatible ART parcel writer: '+name)
            originals=[(root/(name+'.smali')).read_text(encoding='utf-8') for root in roots]
            base=[('compilerFilter','Ljava/lang/String;','writeString'),('compilationReason','Ljava/lang/String;','writeString'),('locationDebugString','Ljava/lang/String;','writeString'),('isBackedByVdexOnly','Z','writeBoolean'),('artifactsLocation','I','writeInt')]
            host_inserted=base[:4]+[('imageLocationDebugString','Ljava/lang/String;','writeString')]+base[4:]
            if status_fields(originals[0])==host_inserted and status_fields(originals[1])==base:
                target=roots[1]/(name+'.smali')
                with target.open('w',encoding='utf-8',newline='\n') as f:f.write(add_host_status_field(originals[1]))
                status_field_adaptations.append({'type':name,'host_inserted_field':'imageLocationDebugString','position':'after isBackedByVdexOnly'})
            elif status_fields(originals[0])==base and status_fields(originals[1])==base+[('dex2oatCmdline','Ljava/lang/String;','writeString')]:
                target=roots[1]/(name+'.smali')
                with target.open('w',encoding='utf-8',newline='\n') as f:f.write(default_status_command(originals[1]))
                status_field_adaptations.append({'type':name,'guest_trailing_field':'dex2oatCmdline','default':''})
            else:raise ValueError('Unexpected status parcel field order')
        for root in roots:
            if wire((root/(name+'.smali')).read_text(encoding='utf-8'))!=wire((roots[0]/(name+'.smali')).read_text(encoding='utf-8')):
                raise ValueError('ART parcel writers remain incompatible: '+name)
    spec=importlib.util.spec_from_file_location('artd',ROOT/'runtime/hyperos-s23/patches/artd_compat.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    proxy=roots[1]/'IArtd$Stub$Proxy.smali';text,report=module.patch(proxy.read_text(encoding='utf-8'),(roots[0]/proxy.name).read_text(encoding='utf-8'))
    with proxy.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
    assembler=out/'assembler';assembler.mkdir();run(javac,'-encoding','UTF-8','-cp',apktool,'-d',assembler,ROOT/'tools/AssembleSmali.java')
    run(java,'-cp',str(assembler)+os.pathsep+str(apktool),'AssembleSmali',out/'guest/smali',out/'classes.dex')
    raw=out/'service-art-unaligned.jar';target=out/'service-art_patched.jar'
    with zipfile.ZipFile(a.guest_jar) as source,zipfile.ZipFile(raw,'w') as z:
        for info in source.infolist():
            entry=copy.copy(info)
            if info.filename=='classes.dex':entry.compress_type=zipfile.ZIP_STORED
            z.writestr(entry,(out/'classes.dex').read_bytes() if info.filename=='classes.dex' else source.read(info))
    align=sdk/'build-tools/35.0.0'/('zipalign'+exe);run(align,'-f','4',raw,target);run(align,'-c','4',target)
    report.update({'state':'candidate-only-device-rpc-and-profile-namespace-validation-pending','source_guest_sha256':a.guest_sha256,'source_host_sha256':a.host_sha256,'parcel_writers_verified':list(WIRE),'status_field_adaptations':status_field_adaptations,'artifact':target.name,'sha256':sha(target),'bytes':target.stat().st_size})
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
