"""Build guest-only HyperOS 4 / SDK37 framework candidates for S23; never deploy.

Native service isolation, MIUI extension review and a complete runtime are still
required. Successful assembly is not a boot or Android verifier result.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,re,subprocess,sys,zipfile
from dynamic_installd_dispatch import patch as dynamic_patch

ROOT=Path(__file__).resolve().parents[1]
PINS_DEFAULT={'services':'242ae9bd14b90961d2aab1b7f12780630112a3fe16394040a546de61d95d544d',
              'framework':'f8af87fa975ca7e529aeeeb193a4e77bea650b0e9b611259e600c248ac3b4bc4'}
PATCHES=['guest_no_vold_keys','skip_host_apex_services','guest_power_guards','guest_storage_guards',
         'guest_installd_abi','guest_no_sysrq_crash','guest_no_weaver','guest_no_biometric_cleanup',
         'guest_no_gatekeeper','guest_pdb_readonly','guest_no_apex_installs','guest_app_id_offset',
         'guest_no_new_users','guest_own_idmap','guest_own_vold']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','host-table','apktool','sdk','java-home','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--services-sha256',default=PINS_DEFAULT['services'])
    p.add_argument('--framework-sha256',default=PINS_DEFAULT['framework'])
    p.add_argument('--jobs',type=int,default=4,help='Apktool decode workers (1-8)')
    p.add_argument('--prepared-trees',type=Path,help='Reuse explicitly prepatched services/framework trees; records reuse, not a clean patch execution')
    p.add_argument('--only-services',action='store_true',help='Rebuild services only; retain a separately verified framework candidate')
    a=p.parse_args();pins={'services':a.services_sha256,'framework':a.framework_sha256}
    if any(not re.fullmatch('[a-f0-9]{64}',value) for value in pins.values()):p.error('Expected SHA-256 source pins')
    if not 1<=a.jobs<=8:p.error('Apktool jobs must be between 1 and 8')
    sources={name:a.inputs/('system-framework-'+name+'.jar') for name in pins}
    for name,path in sources.items():
        if sha(path)!=pins[name]:p.error('Not the inspected HyperOS '+name+' JAR')
    if a.output.exists():p.error('Existing output is preserved')
    a.output.mkdir(parents=True);out=a.output.resolve();sdk=a.sdk.resolve();apktool=a.apktool.resolve()
    exe='.exe' if os.name=='nt' else '';java=a.java_home.resolve()/'bin'/('java'+exe);javac=java.with_name('javac'+exe)
    journal=[];up=ROOT/'runtime/samsung-oneos/upstream/switcher/patches'
    def run(*cmd):subprocess.run([str(x) for x in cmd],check=True)
    def patch(script,*args):
        result=subprocess.run([sys.executable,'-I',str(script),*[str(x) for x in args]],capture_output=True,text=True,encoding='utf-8',errors='replace')
        journal.append({'patch':script.name,'source_sha256':sha(script),'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        (out/'patch-journal.json').write_text(json.dumps(journal,indent=2)+'\n')
        print(script.name+': '+str(result.returncode),flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
    if a.prepared_trees:
        trees={name:(a.prepared_trees/name).resolve() for name in pins}
    else:
        trees={name:out/name for name in pins}
        for name in pins:run(java,'-jar',apktool,'d','-f','-r','-j',str(a.jobs),'-o',trees[name],sources[name].resolve())
        patch(ROOT/'tools/hyperos_no_xspace_repair.py',trees['services'])
        patch(ROOT/'tools/hyperos_guest_lock_stub.py',trees['services'])
        for name in PATCHES:
            args=[trees['services']]+([a.host_table] if name=='guest_installd_abi' else [])
            patch(up/(name+'.py'),*args)
        adapter=list(trees['services'].glob('smali*/com/android/server/display/LocalDisplayAdapter.smali'))
        if len(adapter)!=1:raise RuntimeError('Display adapter not unique')
        patch(up/'display_mode_specs.py',adapter[0])
        for name in ('guest_abi','network_api_flags'):patch(ROOT/('runtime/hyperos-s23/patches/'+name+'.py'),trees['framework'])
    proxies=list(trees['services'].glob('smali*/com/android/server/pm/OneOSInstalldProxy.smali'))
    if len(proxies)!=1:raise RuntimeError('Guarded installd proxy missing')
    proxy=proxies[0];text=proxy.read_text(encoding='utf-8')
    if 'GsionlockedInstalldMap;->code(' not in text:
        text,changed=dynamic_patch(text)
        with proxy.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
    else:changed=[]
    # These checks catch missing preparation; they do not replace the patchers' call-graph checks.
    for suffix,marker in [('com/android/server/pm/UserManagerService.smali','OneOS: no users or profiles in the guest'),
                          ('com/android/server/locksettings/LockSettingsService.smali','OneOS:')]:
        found=list(trees['services'].glob('smali*/'+suffix))
        if len(found)!=1 or marker not in found[0].read_text(encoding='utf-8'):raise RuntimeError('Required guest guard missing: '+suffix)
    helper=out/'helper-classes';helper.mkdir();dex=out/'helper-dex';dex.mkdir();assembler=out/'assembler';assembler.mkdir()
    run(javac,'-encoding','UTF-8','-cp',apktool,'-d',assembler,ROOT/'tools/AssembleSmali.java')
    run(javac,'-encoding','UTF-8','-source','8','-target','8','-cp',sdk/'platforms/android-35/android.jar','-d',helper,ROOT/'runtime/samsung-common/src/GsionlockedInstalldMap.java')
    run(java,'-cp',sdk/'build-tools/35.0.0/lib/d8.jar','com.android.tools.r8.D8','--min-api','31','--lib',sdk/'platforms/android-35/android.jar','--output',dex,*helper.rglob('*.class'))
    artifacts={}
    for name,dirs in {'services':['smali','smali_classes2','smali_classes3'],'framework':['smali_classes3','smali_classes5']}.items():
        if a.only_services and name=='framework':continue
        replaced={}
        for directory in dirs:
            dexname='classes.dex' if directory=='smali' else directory.replace('smali_classes','classes')+'.dex'
            target=out/(name+'-'+dexname)
            run(java,'-Xmx4g','-cp',str(assembler)+os.pathsep+str(apktool),'AssembleSmali',trees[name]/directory,target)
            replaced[dexname]=target
        raw=out/(name+'-unaligned.jar');target=out/(name+'_patched.jar')
        with zipfile.ZipFile(sources[name]) as original,zipfile.ZipFile(raw,'w') as result:
            if not set(replaced).issubset(original.namelist()):raise RuntimeError('Unexpected DEX set')
            for info in original.infolist():
                entry=copy.copy(info)
                if info.filename in replaced:entry.compress_type=zipfile.ZIP_STORED
                result.writestr(entry,replaced[info.filename].read_bytes() if info.filename in replaced else original.read(info))
            if name=='services':
                index=2
                while 'classes'+str(index)+'.dex' in original.namelist():index+=1
                result.write(dex/'classes.dex','classes'+str(index)+'.dex',compress_type=zipfile.ZIP_STORED)
        align=sdk/'build-tools/35.0.0'/('zipalign'+exe)
        run(align,'-f','4',raw,target);run(align,'-c','4',target)
        artifacts[target.name]={'sha256':sha(target),'bytes':target.stat().st_size,'replaced_dex':list(replaced)}
    report={'state':'framework-candidate-only-not-launchable','artifacts':artifacts,'source_sha256':pins,
            'host_table_sha256':sha(a.host_table),'reused_prepared_trees':bool(a.prepared_trees),'dynamic_methods_changed_this_run':changed,
            'remaining':['MIUI extension guards and dependencies','native vold / incremental isolation','guest ART and other module compatibility','HyperOS runtime stage and app profile','device launch and return validation']}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
