import pathlib,subprocess,sys,time,json
b=pathlib.Path(__file__).parent
sys.path.insert(0,str(b/'tests'))
from verify_brand_icon import ico_frames,pe_icons
frames=ico_frames(b/'src/client/assets/dqa.ico')
report=[]
for label,install in [('upgrade',b/'dqa-nondisruptive-icon-final/installed'),('fresh',b/'dqa-nondisruptive-fresh/installed')]:
 if label=='fresh':
  assert not install.exists()
  subprocess.run([str(b/'test-installers/DQAConnect-Setup-1.3.1.exe'),'/SILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=desktopicon,startup','/DIR='+str(install),'/LOG='+str(b/'fresh-install.log')],check=True,timeout=120)
 subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(b/'tests/verify_installed_shell.ps1'),'-InstallRoot',str(install),'-OutputFile',str(b/(label+'-shell.json'))],check=True,timeout=30)
 resources=[pe_icons(install/name,frames) for name in ('DQALauncher.exe','DQAConnect.exe','unins000.exe')]
 uninstall=install/'unins000.exe'
 subprocess.run([str(uninstall),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],timeout=120,check=True)
 time.sleep(2)
 assert not (install/'DQALauncher.exe').exists()
 assert not (install/'DQALauncher.pending.exe').exists()
 assert not (install/'dqa.ico').exists()
 report.append({'case':label,'resources':resources,'uninstall_result':'PASS','launcher_pending_icon_remaining':False})
(b/'install-cleanup.json').write_text(json.dumps({'result':'PASS','cases':report},indent=2))
print('Upgrade and fresh install shortcut/resources/uninstall PASS',flush=True)
